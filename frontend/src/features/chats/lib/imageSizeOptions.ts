export type ImageGenerationSize = "auto" | "1024x1024" | "1536x1024" | "1024x1536";

export interface ImageSizeChoice {
  value: ImageGenerationSize;
  label: string;
}

export const IMAGE_SIZE_OPTIONS: ImageSizeChoice[] = [
  { value: "1024x1024", label: "1024x1024" },
  { value: "1536x1024", label: "1536x1024" },
  { value: "1024x1536", label: "1024x1536" },
  { value: "auto", label: "auto" },
];

export function imageSizeChoiceForValue(value: string): ImageSizeChoice {
  return IMAGE_SIZE_OPTIONS.find((item) => item.value === value) ?? IMAGE_SIZE_OPTIONS[0];
}

export function resolveImageGenerationSize(value: string): ImageGenerationSize {
  return imageSizeChoiceForValue(value).value;
}
