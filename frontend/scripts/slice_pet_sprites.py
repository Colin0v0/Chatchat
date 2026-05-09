from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


FRONTEND_DIR = Path(__file__).resolve().parents[1]
BASE_DIR = FRONTEND_DIR / "public" / "pets" / "fox"
RAW_DIR = BASE_DIR / "raw"
SOURCE_SPRITE = RAW_DIR / "fox_sprites_transparent.png"
FRAME_OUTPUT_DIRS = [
    BASE_DIR / "frames",
    FRONTEND_DIR / "src" / "features" / "pet" / "assets" / "fox" / "frames",
]

CANVAS_SIZE = 256
BOTTOM_PADDING = 12
TARGET_FOOT_Y = CANVAS_SIZE - BOTTOM_PADDING
MAX_ANNOTATION_AREA = 140
MAX_ANNOTATION_SATURATION = 15
BOTTOM_ARTIFACT_TOP = 220
MAX_BOTTOM_ARTIFACT_AREA = 180
MAX_BOTTOM_ARTIFACT_HEIGHT = 18
EDGE_SAMPLE_MIN_ALPHA = 220
OUTLINE_GAP_MIN_OPAQUE_NEIGHBORS = 5
OUTLINE_GAP_FILL_ALPHA = 230
OUTLINE_EDGE_MIN_ALPHA = 72
OUTLINE_EDGE_TARGET_ALPHA = 208
OUTLINE_DIAGONAL_BRIDGE_ALPHA = 222
PRAISE_EXTRA_EDGE_POLISH_PASSES = 2
PRAISE_MANUAL_REPAIRS: dict[int, tuple[tuple[tuple[int, int, int, int], tuple[int, int, int, int]], ...]] = {
    5: (
        ((99, 178, 100, 180), (103, 182, 104, 184)),
        ((137, 181, 138, 183), (133, 185, 134, 187)),
        ((118, 195, 126, 197), (118, 187, 126, 189)),
        ((134, 195, 139, 197), (134, 187, 139, 189)),
    ),
    6: (
        ((104, 176, 109, 181), (104, 168, 109, 173)),
        ((132, 171, 133, 172), (132, 177, 133, 178)),
    ),
}


@dataclass(frozen=True)
class StripCell:
    """一行里单个素材格子的手工边界。"""

    left: int
    right: int


@dataclass(frozen=True)
class AnimationSpec:
    """一个动作最终要导出的帧顺序。"""

    name: str
    frame_indexes: tuple[int, ...]
    scale: float


@dataclass(frozen=True)
class StripSpec:
    """raw 里的一条横向素材带，手工定义真实边界和可复用动作。"""

    top: int
    bottom: int
    cells: tuple[StripCell, ...]
    animations: tuple[AnimationSpec, ...]


STRIP_SPECS: tuple[StripSpec, ...] = (
    StripSpec(
        top=22,
        bottom=108,
        cells=(
            StripCell(17, 145),
            StripCell(145, 272),
            StripCell(272, 396),
            StripCell(396, 523),
            StripCell(523, 649),
            StripCell(649, 774),
            StripCell(774, 901),
            StripCell(901, 1032),
        ),
        animations=(
            AnimationSpec("idle", (2,), 1.22),
        ),
    ),
    StripSpec(
        top=128,
        bottom=211,
        cells=(
            StripCell(16, 143),
            StripCell(143, 268),
            StripCell(268, 393),
            StripCell(393, 524),
            StripCell(524, 653),
            StripCell(653, 778),
            StripCell(778, 907),
            StripCell(907, 1044),
        ),
        animations=(
            AnimationSpec("walk", (1, 2, 3, 4, 5, 6, 7), 1.22),
        ),
    ),
    StripSpec(
        top=231,
        bottom=306,
        cells=(
            StripCell(17, 166),
            StripCell(166, 317),
            StripCell(317, 473),
            StripCell(473, 624),
            StripCell(624, 771),
            StripCell(771, 913),
            StripCell(913, 1059),
        ),
        animations=(
            AnimationSpec("eat", (1, 2, 3, 5, 7), 1.10),
        ),
    ),
    StripSpec(
        top=325,
        bottom=398,
        cells=(
            StripCell(17, 163),
            StripCell(163, 311),
            StripCell(311, 451),
            StripCell(451, 589),
            StripCell(589, 734),
            StripCell(734, 887),
            StripCell(887, 1041),
        ),
        animations=(
            # 中文注释：喝水按用户要求改成先有水后没水，所以顺序从蓝水面帧往回收。
            AnimationSpec("drink", (6, 4, 2), 1.10),
        ),
    ),
    StripSpec(
        top=409,
        bottom=489,
        cells=(
            StripCell(14, 147),
            StripCell(147, 285),
            StripCell(285, 424),
            StripCell(424, 557),
            StripCell(557, 684),
            StripCell(684, 822),
            StripCell(822, 942),
            StripCell(942, 1076),
        ),
        animations=(
            AnimationSpec("sleep", (1, 2, 3, 4, 6, 7), 1.06),
        ),
    ),
    StripSpec(
        top=511,
        bottom=595,
        cells=(
            StripCell(9, 136),
            StripCell(136, 261),
            StripCell(261, 385),
            StripCell(385, 511),
            StripCell(511, 641),
            StripCell(641, 778),
            StripCell(778, 912),
            StripCell(912, 1050),
        ),
        animations=(
            AnimationSpec("emotion", (1, 2, 4, 5), 1.20),
        ),
    ),
    StripSpec(
        top=624,
        bottom=703,
        cells=(
            StripCell(7, 137),
            StripCell(137, 263),
            StripCell(263, 382),
            StripCell(382, 522),
            StripCell(522, 657),
            StripCell(657, 784),
            StripCell(784, 912),
            StripCell(912, 1048),
        ),
        animations=(
            AnimationSpec("sad", (1, 2, 3, 5), 1.16),
            AnimationSpec("surprised", (6, 7, 8, 7), 1.16),
        ),
    ),
    StripSpec(
        top=724,
        bottom=815,
        cells=(
            StripCell(27, 156),
            StripCell(156, 277),
            StripCell(277, 408),
            StripCell(408, 526),
            StripCell(526, 653),
            StripCell(653, 776),
            StripCell(776, 904),
            StripCell(904, 1034),
        ),
        animations=(
            AnimationSpec("pickup", (4, 5, 6, 7), 1.10),
            AnimationSpec("angry", (1, 2, 3, 2), 1.10),
        ),
    ),
    StripSpec(
        top=826,
        bottom=920,
        cells=(
            StripCell(9, 149),
            StripCell(149, 286),
            StripCell(286, 441),
            StripCell(441, 612),
            StripCell(612, 756),
            StripCell(756, 880),
            StripCell(880, 1008),
        ),
        animations=(
            # 中文注释：最后用第 7 格抬头过渡，避免低趴帧结束后直接跳到 idle 站姿。
            AnimationSpec("putdown", (2, 1, 6, 7), 1.08),
        ),
    ),
    StripSpec(
        top=955,
        bottom=1037,
        cells=(
            StripCell(8, 167),
            StripCell(167, 335),
            StripCell(335, 494),
            StripCell(494, 646),
            StripCell(646, 791),
            StripCell(791, 950),
        ),
        animations=(
            AnimationSpec("happy", (2,), 1.18),
        ),
    ),
    StripSpec(
        top=1063,
        bottom=1149,
        cells=(
            StripCell(0, 177),
            StripCell(177, 349),
            StripCell(349, 514),
            StripCell(514, 682),
            StripCell(682, 856),
            StripCell(856, 1039),
        ),
        animations=(
            AnimationSpec("praise", (1, 2, 3, 4, 5, 6), 1.16),
        ),
    ),
    StripSpec(
        top=1180,
        bottom=1266,
        cells=(
            StripCell(0, 152),
            StripCell(152, 322),
            StripCell(322, 493),
            StripCell(493, 660),
            StripCell(660, 833),
            StripCell(833, 1009),
        ),
        animations=(
            AnimationSpec("hurt", (1, 2, 3, 4, 5, 6), 1.16),
        ),
    ),
    StripSpec(
        top=1304,
        bottom=1396,
        cells=(
            StripCell(0, 182),
            StripCell(182, 347),
            StripCell(347, 532),
            StripCell(532, 698),
            StripCell(698, 868),
            StripCell(868, 1060),
        ),
        animations=(
            # 中文注释：用户明确不要第 1 格，这里直接从第 2 格开始挑头身比例更稳的帧。
            AnimationSpec("click", (2, 3, 4, 5, 6), 1.02),
        ),
    ),
)


def remove_small_neutral_components(image: Image.Image) -> Image.Image:
    """去掉编号和灰色碎点，不碰真正的彩色动作特效。"""
    alpha = image.getchannel("A")
    width, height = image.size
    source_pixels = image.load()
    cleaned = image.copy()
    cleaned_pixels = cleaned.load()
    seen: set[tuple[int, int]] = set()

    for y in range(height):
        for x in range(width):
            if alpha.getpixel((x, y)) == 0 or (x, y) in seen:
                continue

            stack = [(x, y)]
            seen.add((x, y))
            points: list[tuple[int, int]] = []
            saturation_sum = 0

            while stack:
                current_x, current_y = stack.pop()
                points.append((current_x, current_y))
                red, green, blue, _ = source_pixels[current_x, current_y]
                saturation_sum += max(red, green, blue) - min(red, green, blue)

                for next_x, next_y in (
                    (current_x + 1, current_y),
                    (current_x - 1, current_y),
                    (current_x, current_y + 1),
                    (current_x, current_y - 1),
                ):
                    if not (0 <= next_x < width and 0 <= next_y < height):
                        continue

                    if (next_x, next_y) in seen:
                        continue

                    if alpha.getpixel((next_x, next_y)) == 0:
                        continue

                    seen.add((next_x, next_y))
                    stack.append((next_x, next_y))

            average_saturation = saturation_sum / len(points)
            if len(points) <= MAX_ANNOTATION_AREA and average_saturation <= MAX_ANNOTATION_SATURATION:
                for point_x, point_y in points:
                    cleaned_pixels[point_x, point_y] = (0, 0, 0, 0)

    return cleaned


def extract_cell_frame(sheet: Image.Image, strip: StripSpec, frame_index: int) -> Image.Image:
    """从指定 strip 的指定格子里手工抽帧。"""
    row_crop = sheet.crop((0, strip.top, sheet.width, strip.bottom))
    cell = strip.cells[frame_index - 1]
    cell_crop = row_crop.crop((cell.left, 0, cell.right, row_crop.height))
    frame = remove_small_neutral_components(cell_crop)
    frame_bbox = frame.getbbox()
    if frame_bbox is None:
        raise RuntimeError(f"empty cleaned frame at strip={strip.top}-{strip.bottom}, frame={frame_index}")

    return frame.crop(frame_bbox)


def build_frame(frame: Image.Image, scale: float, animation_name: str) -> Image.Image:
    """统一缩放并贴到底边，保证整套狐狸的落地位置稳定。"""
    scaled_width = round(frame.width * scale)
    scaled_height = round(frame.height * scale)
    scaled_frame = frame.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
    frame_bbox = scaled_frame.getbbox()
    if frame_bbox is None:
        raise RuntimeError("empty scaled frame")

    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    paste_x = round((CANVAS_SIZE - scaled_frame.width) / 2)
    paste_y = TARGET_FOOT_Y - frame_bbox[3]
    canvas.alpha_composite(scaled_frame, (paste_x, paste_y))
    remove_ground_shadow(canvas, preserve_props=animation_name in {"eat", "drink"})
    return canvas


def remove_ground_shadow(image: Image.Image, preserve_props: bool = False) -> None:
    """清理底部蓝灰色地面投影，保留水碗、盘子、爪子这类主体像素。"""
    pixels = image.load()
    for y in range(222, image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                continue

            # 中文注释：投影集中在底部蓝灰色范围；盘子/水碗颜色更亮或更饱和，不走这条清理规则。
            if (
                35 <= red <= 125
                and 48 <= green <= 150
                and 72 <= blue <= 185
                and blue >= red + 18
                and green >= red + 8
                and blue >= green + 18
            ):
                pixels[x, y] = (0, 0, 0, 0)

    remove_bottom_artifacts(image)
    if not preserve_props:
        remove_bottom_floor_halo(image)


def remove_bottom_artifacts(image: Image.Image) -> None:
    """删掉脚底附近与主体断开的浅色碎块，专门处理残留阴影描边。"""
    alpha = image.getchannel("A")
    pixels = image.load()
    width, height = image.size
    seen: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []

    for y in range(height):
        for x in range(width):
            if alpha.getpixel((x, y)) == 0 or (x, y) in seen:
                continue

            stack = [(x, y)]
            seen.add((x, y))
            points: list[tuple[int, int]] = []

            while stack:
                current_x, current_y = stack.pop()
                points.append((current_x, current_y))

                for next_x, next_y in (
                    (current_x + 1, current_y),
                    (current_x - 1, current_y),
                    (current_x, current_y + 1),
                    (current_x, current_y - 1),
                ):
                    if not (0 <= next_x < width and 0 <= next_y < height):
                        continue

                    if (next_x, next_y) in seen:
                        continue

                    if alpha.getpixel((next_x, next_y)) == 0:
                        continue

                    seen.add((next_x, next_y))
                    stack.append((next_x, next_y))

            components.append(points)

    if not components:
        return

    # 中文注释：最大连通块就是狐狸主体，底部残影都是与主体断开的独立小块。
    largest_component = max(components, key=len)

    for points in components:
        if points is largest_component:
            continue

        if not should_remove_bottom_artifact(points):
            continue

        for point_x, point_y in points:
            pixels[point_x, point_y] = (0, 0, 0, 0)


def should_remove_bottom_artifact(points: list[tuple[int, int]]) -> bool:
    """只命中脚底断开的碎块，不碰盘子、水碗或狐狸主体上的高光。"""
    if not points:
        return False

    xs = [point_x for point_x, _ in points]
    ys = [point_y for _, point_y in points]
    bbox_top = min(ys)
    bbox_bottom = max(ys)
    bbox_height = bbox_bottom - bbox_top + 1

    if bbox_top < BOTTOM_ARTIFACT_TOP:
        return False

    if len(points) > MAX_BOTTOM_ARTIFACT_AREA or bbox_height > MAX_BOTTOM_ARTIFACT_HEIGHT:
        return False

    # 中文注释：这里处理的都是已经与最大主体断开的连通块；只要落在脚底带内，就视为残留碎点直接清掉。
    return True


def remove_bottom_floor_halo(image: Image.Image) -> None:
    """强力清掉无道具动作底边的蓝灰/白色光晕，避免脚底像踩着一层影子。"""
    pixels = image.load()
    for y in range(224, image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                continue

            if not is_floor_halo_pixel(red, green, blue):
                continue

            pixels[x, y] = (0, 0, 0, 0)


def is_floor_halo_pixel(red: int, green: int, blue: int) -> bool:
    """命中底部冷色投影和近白色描边，不碰偏黄的毛发高光。"""
    average_brightness = (red + green + blue) / 3
    is_cool_shadow = (
        blue >= red + 8
        and green >= red
        and blue >= green + 4
    )
    is_light_neutral_halo = (
        average_brightness >= 185
        and abs(red - green) <= 20
        and abs(green - blue) <= 20
        and green >= red - 2
        and blue >= red - 2
    )
    return is_cool_shadow or is_light_neutral_halo


def polish_sprite_edges(image: Image.Image) -> None:
    """统一修边：透明边缘做颜色外扩，半透明边做去白边，小断线做闭合。"""
    bleed_transparent_edge_colors(image)
    recolor_semitransparent_edge_pixels(image)
    normalize_outline_edge_pixels(image)
    close_outline_gaps(image)
    bridge_diagonal_outline_gaps(image)


def bleed_transparent_edge_colors(image: Image.Image) -> None:
    """把主体颜色外扩到透明边缘，避免浏览器缩放时采到旧底色产生毛边。"""
    source = image.copy()
    source_pixels = source.load()
    source_alpha = source.getchannel("A")
    target_pixels = image.load()

    for y in range(image.height):
        for x in range(image.width):
            if source_alpha.getpixel((x, y)) != 0:
                continue

            neighbor_colors = collect_neighbor_colors(source_pixels, source_alpha, x, y)
            if not neighbor_colors:
                continue

            average_red, average_green, average_blue = average_rgb(neighbor_colors)
            target_pixels[x, y] = (average_red, average_green, average_blue, 0)


def recolor_semitransparent_edge_pixels(image: Image.Image) -> None:
    """把边缘半透明像素改成附近主体颜色，去掉抠图留下的灰白边。"""
    source = image.copy()
    source_pixels = source.load()
    source_alpha = source.getchannel("A")
    target_pixels = image.load()

    for y in range(image.height):
        for x in range(image.width):
            alpha = source_alpha.getpixel((x, y))
            if not (0 < alpha < 255):
                continue

            neighbor_colors = collect_neighbor_colors(source_pixels, source_alpha, x, y)
            if len(neighbor_colors) < 2:
                continue

            average_red, average_green, average_blue = average_rgb(neighbor_colors)
            target_pixels[x, y] = (average_red, average_green, average_blue, alpha)


def normalize_outline_edge_pixels(image: Image.Image) -> None:
    """把发灰、发虚的描边统一成邻域里的真实线条颜色，减少粗糙断裂感。"""
    source = image.copy()
    source_pixels = source.load()
    source_alpha = source.getchannel("A")
    target_pixels = image.load()

    for y in range(1, image.height - 1):
        for x in range(1, image.width - 1):
            alpha = source_alpha.getpixel((x, y))
            if not (OUTLINE_EDGE_MIN_ALPHA <= alpha < 255):
                continue

            dark_neighbors: list[tuple[int, int, int]] = []
            for next_x, next_y in iter_neighbor_points(x, y, image.width, image.height):
                next_alpha = source_alpha.getpixel((next_x, next_y))
                if next_alpha < EDGE_SAMPLE_MIN_ALPHA:
                    continue

                red, green, blue, _ = source_pixels[next_x, next_y]
                if is_dark_outline_color(red, green, blue):
                    dark_neighbors.append((red, green, blue))

            if len(dark_neighbors) < 2:
                continue

            red, green, blue, _ = source_pixels[x, y]
            if is_dark_outline_color(red, green, blue):
                continue

            average_red, average_green, average_blue = average_rgb(dark_neighbors)
            target_pixels[x, y] = (
                average_red,
                average_green,
                average_blue,
                max(alpha, OUTLINE_EDGE_TARGET_ALPHA),
            )


def close_outline_gaps(image: Image.Image) -> None:
    """补齐 1px 级别的小断线，让黑色外轮廓不要一截一截地碎开。"""
    source = image.copy()
    source_pixels = source.load()
    source_alpha = source.getchannel("A")
    target_pixels = image.load()

    for y in range(1, image.height - 1):
        for x in range(1, image.width - 1):
            if source_alpha.getpixel((x, y)) != 0:
                continue

            opaque_neighbors: list[tuple[int, int, int]] = []
            dark_neighbors: list[tuple[int, int, int]] = []
            left_dark = False
            right_dark = False
            top_dark = False
            bottom_dark = False

            for next_x, next_y in iter_neighbor_points(x, y, image.width, image.height):
                next_alpha = source_alpha.getpixel((next_x, next_y))
                if next_alpha < EDGE_SAMPLE_MIN_ALPHA:
                    continue

                red, green, blue, _ = source_pixels[next_x, next_y]
                opaque_neighbors.append((red, green, blue))
                if not is_dark_outline_color(red, green, blue):
                    continue

                dark_neighbors.append((red, green, blue))
                if next_x < x:
                    left_dark = True
                if next_x > x:
                    right_dark = True
                if next_y < y:
                    top_dark = True
                if next_y > y:
                    bottom_dark = True

            if len(opaque_neighbors) < OUTLINE_GAP_MIN_OPAQUE_NEIGHBORS or len(dark_neighbors) < 2:
                continue

            if not ((left_dark and right_dark) or (top_dark and bottom_dark)):
                continue

            average_red, average_green, average_blue = average_rgb(dark_neighbors)
            target_pixels[x, y] = (average_red, average_green, average_blue, OUTLINE_GAP_FILL_ALPHA)


def bridge_diagonal_outline_gaps(image: Image.Image) -> None:
    """补对角线上的小豁口，避免轮廓像锯齿一样一格一格断开。"""
    source = image.copy()
    source_pixels = source.load()
    source_alpha = source.getchannel("A")
    target_pixels = image.load()

    for y in range(1, image.height - 1):
        for x in range(1, image.width - 1):
            if source_alpha.getpixel((x, y)) != 0:
                continue

            top_left = get_dark_outline_neighbor(source_pixels, source_alpha, x - 1, y - 1)
            top_right = get_dark_outline_neighbor(source_pixels, source_alpha, x + 1, y - 1)
            bottom_left = get_dark_outline_neighbor(source_pixels, source_alpha, x - 1, y + 1)
            bottom_right = get_dark_outline_neighbor(source_pixels, source_alpha, x + 1, y + 1)
            left = get_dark_outline_neighbor(source_pixels, source_alpha, x - 1, y)
            right = get_dark_outline_neighbor(source_pixels, source_alpha, x + 1, y)
            top = get_dark_outline_neighbor(source_pixels, source_alpha, x, y - 1)
            bottom = get_dark_outline_neighbor(source_pixels, source_alpha, x, y + 1)

            bridge_colors: list[tuple[int, int, int]] = []

            # 中文注释：两条对角轮廓都在这里“擦肩而过”时，补 1px 会让边缘更顺。
            if top_left and bottom_right and (left or top or right or bottom):
                bridge_colors.extend((top_left, bottom_right))
            if top_right and bottom_left and (left or top or right or bottom):
                bridge_colors.extend((top_right, bottom_left))

            if not bridge_colors:
                continue

            average_red, average_green, average_blue = average_rgb(bridge_colors)
            target_pixels[x, y] = (
                average_red,
                average_green,
                average_blue,
                OUTLINE_DIAGONAL_BRIDGE_ALPHA,
            )


def collect_neighbor_colors(
    pixels: Image.PixelAccess,
    alpha: Image.Image,
    x: int,
    y: int,
) -> list[tuple[int, int, int]]:
    """采样附近实心主体颜色，给边缘像素做统一修色。"""
    colors: list[tuple[int, int, int]] = []
    for next_x, next_y in iter_neighbor_points(x, y, alpha.width, alpha.height):
        if alpha.getpixel((next_x, next_y)) < EDGE_SAMPLE_MIN_ALPHA:
            continue

        red, green, blue, _ = pixels[next_x, next_y]
        colors.append((red, green, blue))
    return colors


def get_dark_outline_neighbor(
    pixels: Image.PixelAccess,
    alpha: Image.Image,
    x: int,
    y: int,
) -> tuple[int, int, int] | None:
    """安全读取一个深色描边邻居，不符合条件就直接跳过。"""
    if not (0 <= x < alpha.width and 0 <= y < alpha.height):
        return None

    if alpha.getpixel((x, y)) < EDGE_SAMPLE_MIN_ALPHA:
        return None

    red, green, blue, _ = pixels[x, y]
    if not is_dark_outline_color(red, green, blue):
        return None

    return red, green, blue


def iter_neighbor_points(x: int, y: int, width: int, height: int):
    """按 8 邻域遍历，统一给修边步骤复用。"""
    for delta_y in (-1, 0, 1):
        for delta_x in (-1, 0, 1):
            if delta_x == 0 and delta_y == 0:
                continue

            next_x = x + delta_x
            next_y = y + delta_y
            if 0 <= next_x < width and 0 <= next_y < height:
                yield next_x, next_y


def average_rgb(colors: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    """给一组采样色求平均，作为边缘补色结果。"""
    return (
        round(sum(color[0] for color in colors) / len(colors)),
        round(sum(color[1] for color in colors) / len(colors)),
        round(sum(color[2] for color in colors) / len(colors)),
    )


def is_dark_outline_color(red: int, green: int, blue: int) -> bool:
    """识别深色外轮廓，专门用于补 1px 断线。"""
    return max(red, green, blue) <= 96


def retouch_known_artifacts(image: Image.Image, animation_name: str, output_index: int) -> None:
    """统一修掉已经确认的素材瑕疵，避免每次重切后又回到旧问题。"""
    if animation_name == "praise" and output_index in {5, 6}:
        normalize_praise_face_highlights(image)


def refine_praise_frame(image: Image.Image, output_index: int) -> None:
    """夸夸动作单独再收一轮边，让脸和爪子的线条更连贯。"""
    apply_manual_praise_repairs(image, output_index)
    for _ in range(PRAISE_EXTRA_EDGE_POLISH_PASSES):
        recolor_semitransparent_edge_pixels(image)
        normalize_outline_edge_pixels(image)
        close_outline_gaps(image)
        bridge_diagonal_outline_gaps(image)

    # 中文注释：第五、第六帧额头高光最突兀，再补一次局部毛色修平。
    if output_index in {5, 6}:
        normalize_praise_face_highlights(image)


def apply_manual_praise_repairs(image: Image.Image, output_index: int) -> None:
    """把 praise 里固定位置的白高光直接用附近橙毛覆盖，收掉最扎眼的瑕疵。"""
    repairs = PRAISE_MANUAL_REPAIRS.get(output_index, ())
    if not repairs:
        return

    for target_box, donor_box in repairs:
        paint_patch_from_donor_box(image, target_box, donor_box)


def paint_patch_from_donor_box(
    image: Image.Image,
    target_box: tuple[int, int, int, int],
    donor_box: tuple[int, int, int, int],
) -> None:
    """按相对位置把 donor 区域贴到 target 区域，适合修固定小瑕疵。"""
    pixels = image.load()
    target_left, target_top, target_right, target_bottom = target_box
    donor_left, donor_top, donor_right, donor_bottom = donor_box
    target_width = target_right - target_left + 1
    target_height = target_bottom - target_top + 1
    donor_width = donor_right - donor_left + 1
    donor_height = donor_bottom - donor_top + 1

    for delta_y in range(target_height):
        for delta_x in range(target_width):
            source_x = donor_left + min(donor_width - 1, round(delta_x * (donor_width - 1) / max(1, target_width - 1)))
            source_y = donor_top + min(donor_height - 1, round(delta_y * (donor_height - 1) / max(1, target_height - 1)))
            pixels[target_left + delta_x, target_top + delta_y] = pixels[source_x, source_y]


def normalize_praise_face_highlights(image: Image.Image) -> None:
    """移除 praise-05/06 额头上突兀的白色高光，保留眼睛和耳朵的正常亮点。"""
    pixels = image.load()
    alpha = image.getchannel("A")
    region_left, region_top, region_right, region_bottom = 92, 146, 164, 198
    seen: set[tuple[int, int]] = set()

    for y in range(region_top, region_bottom):
        for x in range(region_left, region_right):
            if (x, y) in seen or alpha.getpixel((x, y)) == 0:
                continue

            red, green, blue, _ = pixels[x, y]
            if not is_praise_highlight_pixel(red, green, blue):
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
                    if not (region_left <= next_x < region_right and region_top <= next_y < region_bottom):
                        continue

                    if (next_x, next_y) in seen or alpha.getpixel((next_x, next_y)) == 0:
                        continue

                    next_red, next_green, next_blue, _ = pixels[next_x, next_y]
                    if not is_praise_highlight_pixel(next_red, next_green, next_blue):
                        continue

                    seen.add((next_x, next_y))
                    stack.append((next_x, next_y))

            component_left = min(point[0] for point in component)
            component_top = min(point[1] for point in component)
            component_right = max(point[0] for point in component)
            component_bottom = max(point[1] for point in component)
            component_width = component_right - component_left + 1
            component_height = component_bottom - component_top + 1
            component_points = set(component)
            orange_border_count = 0
            dark_border_count = 0
            for point_x, point_y in component:
                for next_x, next_y in (
                    (point_x + 1, point_y),
                    (point_x - 1, point_y),
                    (point_x, point_y + 1),
                    (point_x, point_y - 1),
                    (point_x + 1, point_y + 1),
                    (point_x + 1, point_y - 1),
                    (point_x - 1, point_y + 1),
                    (point_x - 1, point_y - 1),
                ):
                    if not (0 <= next_x < image.width and 0 <= next_y < image.height):
                        continue

                    if (next_x, next_y) in component_points or alpha.getpixel((next_x, next_y)) < EDGE_SAMPLE_MIN_ALPHA:
                        continue

                    next_red, next_green, next_blue, _ = pixels[next_x, next_y]
                    if is_praise_highlight_donor_color(next_red, next_green, next_blue):
                        orange_border_count += 1
                    elif is_dark_outline_color(next_red, next_green, next_blue):
                        dark_border_count += 1

            is_forehead_highlight = (
                3 <= len(component) <= 24
                and component_width <= 12
                and component_height <= 8
                and 96 <= component_left
                and component_right <= 149
                and 170 <= component_top
                and component_bottom <= 197
                and orange_border_count >= max(6, len(component))
                and orange_border_count >= dark_border_count * 2
            )
            # 中文注释：只修额头橙毛上的高光，不碰眼睛高光、白毛和爱心。
            if not is_forehead_highlight:
                continue

            for point_x, point_y in component:
                donor_color = find_praise_highlight_donor_pixel(
                    pixels,
                    alpha,
                    point_x,
                    point_y,
                    image.width,
                    image.height,
                )
                if donor_color is None:
                    continue

                pixels[point_x, point_y] = donor_color


def find_praise_highlight_donor_pixel(
    pixels: Image.PixelAccess,
    alpha: Image.Image,
    point_x: int,
    point_y: int,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int] | None:
    """从额头下方逐像素找橙毛，把 praise 的白点直接贴回去。"""
    for delta_y in range(4, 13):
        sample_y = point_y + delta_y
        if sample_y >= image_height:
            break

        for delta_x in (0, -1, 1, -2, 2):
            sample_x = point_x + delta_x
            if not (0 <= sample_x < image_width):
                continue

            if alpha.getpixel((sample_x, sample_y)) < EDGE_SAMPLE_MIN_ALPHA:
                continue

            color = pixels[sample_x, sample_y]
            if is_praise_highlight_donor_color(color[0], color[1], color[2]):
                return color

    return None


def is_praise_highlight_pixel(red: int, green: int, blue: int) -> bool:
    """只抓那种额头上的亮白高光，不碰眼睛高光和耳朵白毛。"""
    average_brightness = (red + green + blue) / 3
    return (
        average_brightness >= 220
        and abs(red - green) <= 42
        and abs(green - blue) <= 42
    )


def is_orange_fur_pixel(red: int, green: int, blue: int) -> bool:
    """狐狸毛色范围，用来给高光修补时取邻域底色。"""
    return red >= 180 and green >= 95 and green <= 205 and blue <= 120 and red >= green + 24


def is_praise_highlight_donor_color(red: int, green: int, blue: int) -> bool:
    """给额头补色时只取正常橙毛，不把白毛和爱心高光也采进来。"""
    average_brightness = (red + green + blue) / 3
    return (
        red >= 205
        and 105 <= green <= 205
        and blue <= 110
        and red >= green + 20
        and average_brightness <= 190
    )


def clear_output_dirs() -> None:
    """整套重切前直接清空旧目录，保证只留下新素材。"""
    for output_dir in FRAME_OUTPUT_DIRS:
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)


def save_animation_frames(sheet: Image.Image, strip: StripSpec, animation: AnimationSpec) -> None:
    """导出一个动作的所有帧。"""
    output_dirs = [output_root / animation.name for output_root in FRAME_OUTPUT_DIRS]
    for output_dir in output_dirs:
        output_dir.mkdir(parents=True, exist_ok=True)

    for output_index, frame_index in enumerate(animation.frame_indexes, start=1):
        frame = extract_cell_frame(sheet, strip, frame_index)
        canvas = build_frame(frame, animation.scale, animation.name)
        retouch_known_artifacts(canvas, animation.name, output_index)
        polish_sprite_edges(canvas)
        if animation.name == "praise":
            refine_praise_frame(canvas, output_index)
        for output_dir in output_dirs:
            canvas.save(output_dir / f"{animation.name}-{output_index:02d}.png")


def main() -> None:
    if not SOURCE_SPRITE.exists():
        raise FileNotFoundError(f"missing source sprite sheet: {SOURCE_SPRITE}")

    # 中文注释：这次只认用户最新放进 raw 的透明大图，不再读任何旧狐狸原图。
    sheet = Image.open(SOURCE_SPRITE).convert("RGBA")
    clear_output_dirs()

    for strip in STRIP_SPECS:
        for animation in strip.animations:
            save_animation_frames(sheet, strip, animation)


if __name__ == "__main__":
    main()
