from pathlib import Path

from PIL import Image


FRONTEND_DIR = Path(__file__).resolve().parents[1]
BASE_DIR = FRONTEND_DIR / "public" / "pets" / "fox"
RAW_DIR = BASE_DIR / "raw"
FRAME_OUTPUT_DIRS = [
    BASE_DIR / "frames",
    FRONTEND_DIR / "src" / "features" / "pet" / "assets" / "fox" / "frames",
]
CANVAS_SIZE = 256
BOTTOM_PADDING = 12
SINGLE_BODY_ANIMATIONS = {"drink", "eat", "idle", "pickup", "walk"}
IDLE_EYE_REFERENCE_BOX = (165, 177, 310, 319)
WALK_EYE_SEARCH_BOX = (108, 158, 178, 190)
WALK_EYE_PATCH_PADDING = (7, 6, 7, 5)


def keep_largest_alpha_component(image: Image.Image) -> Image.Image:
    """只保留主体组件，清掉切进来的隔壁帧尾巴和零散脏点。"""
    alpha = image.getchannel("A")
    width, height = image.size
    seen: set[tuple[int, int]] = set()
    components: list[set[tuple[int, int]]] = []

    for y in range(height):
        for x in range(width):
            if alpha.getpixel((x, y)) == 0 or (x, y) in seen:
                continue

            component: set[tuple[int, int]] = set()
            stack = [(x, y)]
            seen.add((x, y))

            while stack:
                current_x, current_y = stack.pop()
                component.add((current_x, current_y))

                for next_x, next_y in (
                    (current_x + 1, current_y),
                    (current_x - 1, current_y),
                    (current_x, current_y + 1),
                    (current_x, current_y - 1),
                ):
                    if (
                        0 <= next_x < width
                        and 0 <= next_y < height
                        and (next_x, next_y) not in seen
                        and alpha.getpixel((next_x, next_y)) > 0
                    ):
                        seen.add((next_x, next_y))
                        stack.append((next_x, next_y))

            components.append(component)

    if not components:
        raise RuntimeError("empty sprite after component cleanup")

    main_component = max(components, key=len)
    cleaned = Image.new("RGBA", image.size, (0, 0, 0, 0))
    source_pixels = image.load()
    cleaned_pixels = cleaned.load()

    for x, y in main_component:
        cleaned_pixels[x, y] = source_pixels[x, y]

    return cleaned


def build_centered_canvas(sheet: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    """按原来的单帧居中规则生成一张标准画布。"""
    crop = sheet.crop(box)
    bbox = crop.getbbox()
    if bbox is None:
        raise RuntimeError(f"empty crop for reference: {box}")

    sprite = crop.crop(bbox)
    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    x = (CANVAS_SIZE - sprite.width) // 2
    y = CANVAS_SIZE - sprite.height - BOTTOM_PADDING
    if x < 0 or y < 0:
        raise RuntimeError(f"reference sprite too large: {sprite.size}")

    canvas.alpha_composite(sprite, (x, y))
    return keep_largest_alpha_component(canvas)


def find_walk_eye_boxes(image: Image.Image) -> list[tuple[int, int, int, int]]:
    """定位走路帧里的两只眼睛，后续用同一套眼睛贴片统一大小。"""
    alpha = image.getchannel("A")
    pixels = image.load()
    left, top, right, bottom = WALK_EYE_SEARCH_BOX
    seen: set[tuple[int, int]] = set()
    components: list[tuple[int, tuple[int, int, int, int]]] = []

    for y in range(top, bottom):
        for x in range(left, right):
            red, green, blue, _ = pixels[x, y]
            if alpha.getpixel((x, y)) == 0 or max(red, green, blue) > 55 or (x, y) in seen:
                continue

            stack = [(x, y)]
            seen.add((x, y))
            component: list[tuple[int, int]] = []

            while stack:
                current_x, current_y = stack.pop()
                component.append((current_x, current_y))

                for next_x, next_y in (
                    (current_x + 1, current_y),
                    (current_x - 1, current_y),
                    (current_x, current_y + 1),
                    (current_x, current_y - 1),
                ):
                    if not (left <= next_x < right and top <= next_y < bottom):
                        continue

                    if (next_x, next_y) in seen:
                        continue

                    next_red, next_green, next_blue, _ = pixels[next_x, next_y]
                    if alpha.getpixel((next_x, next_y)) > 0 and max(next_red, next_green, next_blue) <= 55:
                        seen.add((next_x, next_y))
                        stack.append((next_x, next_y))

            xs = [point_x for point_x, _ in component]
            ys = [point_y for _, point_y in component]
            box = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
            width = box[2] - box[0]
            height = box[3] - box[1]
            if len(component) >= 60 and 8 <= width <= 18 and 10 <= height <= 22:
                components.append((len(component), box))

    if len(components) < 2:
        raise RuntimeError("walk eye detection failed")

    eye_boxes = [box for _, box in sorted(components, reverse=True)[:2]]
    return sorted(eye_boxes, key=lambda box: box[0])


def normalize_walk_eyes(frames: list[Image.Image], reference: Image.Image) -> list[Image.Image]:
    """把走路动画的眼睛统一成待机那套贴片，避免走路时眼睛一会大一会小。"""
    reference_eye_boxes = find_walk_eye_boxes(reference)
    pad_left, pad_top, pad_right, pad_bottom = WALK_EYE_PATCH_PADDING
    eye_patches: list[Image.Image] = []
    reference_patch_centers: list[tuple[float, float]] = []

    for box in reference_eye_boxes:
        patch_box = (
            box[0] - pad_left,
            box[1] - pad_top,
            box[2] + pad_right,
            box[3] + pad_bottom,
        )
        eye_patches.append(reference.crop(patch_box))
        reference_patch_centers.append(
            (
                (box[0] + box[2]) / 2 - patch_box[0],
                (box[1] + box[3]) / 2 - patch_box[1],
            ),
        )

    normalized_frames: list[Image.Image] = []
    for frame in frames:
        normalized = frame.copy()
        frame_eye_boxes = find_walk_eye_boxes(frame)

        for eye_box, eye_patch, patch_center in zip(frame_eye_boxes, eye_patches, reference_patch_centers):
            eye_center_x = (eye_box[0] + eye_box[2]) / 2
            eye_center_y = (eye_box[1] + eye_box[3]) / 2
            paste_x = round(eye_center_x - patch_center[0])
            paste_y = round(eye_center_y - patch_center[1])
            normalized.alpha_composite(eye_patch, (paste_x, paste_y))

        normalized_frames.append(normalized)

    return normalized_frames


def save_frames(animation: str, sheet: Image.Image, boxes: list[tuple[int, int, int, int]]) -> None:
    """把原始大图按坐标切成统一尺寸的小帧。"""
    output_dirs = [frames_dir / animation for frames_dir in FRAME_OUTPUT_DIRS]
    for output_dir in output_dirs:
        output_dir.mkdir(parents=True, exist_ok=True)

        for old_frame in output_dir.glob("*.png"):
            old_frame.unlink()

    for index, box in enumerate(boxes, start=1):
        crop = sheet.crop(box)
        bbox = crop.getbbox()
        if bbox is None:
            raise RuntimeError(f"empty crop: {animation} #{index} {box}")

        sprite = crop.crop(bbox)
        canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
        x = (CANVAS_SIZE - sprite.width) // 2
        y = CANVAS_SIZE - sprite.height - BOTTOM_PADDING
        if x < 0 or y < 0:
            raise RuntimeError(f"sprite too large: {animation} #{index} {sprite.size}")

        canvas.alpha_composite(sprite, (x, y))
        if animation in SINGLE_BODY_ANIMATIONS:
            canvas = keep_largest_alpha_component(canvas)

        for output_dir in output_dirs:
            canvas.save(output_dir / f"{animation}-{index:02d}.png")


def save_cell_aligned_frames(animation: str, sheet: Image.Image, boxes: list[tuple[int, int, int, int]]) -> None:
    """保留每格里的相对位置，适合走路这种需要身体重心连续变化的动作。"""
    output_dirs = [frames_dir / animation for frames_dir in FRAME_OUTPUT_DIRS]
    for output_dir in output_dirs:
        output_dir.mkdir(parents=True, exist_ok=True)

        for old_frame in output_dir.glob("*.png"):
            old_frame.unlink()

    canvases: list[Image.Image] = []
    for index, box in enumerate(boxes, start=1):
        crop = sheet.crop(box)
        bbox = crop.getbbox()
        if bbox is None:
            raise RuntimeError(f"empty crop: {animation} #{index} {box}")

        canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
        x = (CANVAS_SIZE - crop.width) // 2
        y = CANVAS_SIZE - crop.height - BOTTOM_PADDING
        if x < 0 or y < 0:
            raise RuntimeError(f"sprite cell too large: {animation} #{index} {crop.size}")

        canvas.alpha_composite(crop, (x, y))
        canvas = keep_largest_alpha_component(canvas)
        canvases.append(canvas)

    if animation == "walk":
        reference_canvas = build_centered_canvas(sheet, IDLE_EYE_REFERENCE_BOX)
        canvases = normalize_walk_eyes(canvases, reference_canvas)

    for index, canvas in enumerate(canvases, start=1):
        for output_dir in output_dirs:
            canvas.save(output_dir / f"{animation}-{index:02d}.png")


def main() -> None:
    # thread-image-02 是生活/互动动作，thread-image-03 是基础循环动作。
    actions_sheet = Image.open(RAW_DIR / "thread-image-02.png").convert("RGBA")
    basic_sheet = Image.open(RAW_DIR / "thread-image-03.png").convert("RGBA")
    # thread-image-04 是补充动作表。只取干净主体区域，避开每格下面的编号文字。
    extra_sheet = Image.open(RAW_DIR / "thread-image-04.png").convert("RGBA")

    save_frames("idle", basic_sheet, [
        (165, 177, 310, 319), (310, 177, 440, 319), (440, 177, 570, 319),
        (570, 177, 710, 319), (710, 177, 850, 319), (850, 177, 1000, 319),
    ])
    save_cell_aligned_frames("walk", basic_sheet, [
        # 走路不能按主体重新居中，否则身体像被钉在原地，只剩脚在切帧。
        (160, 360, 310, 487), (300, 360, 450, 487), (435, 360, 585, 487),
        (565, 360, 715, 487), (705, 360, 855, 487), (845, 360, 995, 487),
    ])
    save_frames("sleep", basic_sheet, [
        (165, 552, 320, 671), (320, 552, 480, 671), (480, 552, 630, 671),
        (630, 552, 790, 671), (790, 552, 1000, 671),
    ])
    save_frames("happy", basic_sheet, [
        (165, 726, 320, 855), (320, 726, 465, 855), (465, 726, 630, 855),
        (630, 726, 800, 855), (800, 726, 1000, 855), (165, 903, 320, 1039),
        (320, 903, 465, 1039), (465, 903, 630, 1039), (630, 903, 800, 1039),
        (800, 903, 1000, 1039),
    ])
    save_frames("click", basic_sheet, [
        (300, 1064, 465, 1231), (465, 1064, 635, 1231), (635, 1064, 810, 1231),
    ])

    save_frames("eat", actions_sheet, [
        (285, 240, 438, 375), (440, 240, 575, 375), (585, 240, 725, 375),
        (725, 240, 865, 375), (865, 240, 1000, 375),
    ])
    save_frames("drink", actions_sheet, [
        (285, 408, 435, 527), (435, 408, 575, 527), (575, 408, 725, 527),
        (725, 408, 865, 527), (865, 408, 1000, 527),
    ])
    save_frames("emotion", actions_sheet, [
        (275, 560, 430, 687), (430, 560, 575, 687), (575, 560, 725, 687),
        (725, 560, 865, 687), (865, 560, 1000, 687),
    ])
    save_frames("pickup", extra_sheet, [
        # Pick Up 第 5 格贴着原图右边界，容易带邻居碎片；前 4 格作为抬起过程更干净。
        (195, 62, 345, 226), (345, 62, 520, 226), (515, 62, 675, 226),
        (660, 62, 820, 226),
    ])
    save_frames("putdown", actions_sheet, [
        (600, 735, 790, 920), (790, 735, 1010, 920),
    ])
    save_frames("praise", actions_sheet, [
        (50, 1040, 190, 1190), (240, 1040, 375, 1190), (410, 1040, 600, 1190),
        (600, 1040, 790, 1190), (50, 1290, 200, 1415), (300, 1290, 520, 1415),
        (520, 1290, 760, 1415),
    ])
    save_frames("hurt", actions_sheet, [
        (790, 1040, 1000, 1190), (770, 1290, 980, 1415),
    ])


if __name__ == "__main__":
    main()
