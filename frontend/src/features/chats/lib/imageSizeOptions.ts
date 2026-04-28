export type ImageGenerationSize = "auto" | "1024x1024" | "1536x1024" | "1024x1536";
export type ImageGenerationQuality = "auto" | "low" | "medium" | "high";
export type ImageGenerationOutputFormat = "png" | "jpeg" | "webp";

export interface ImageSizeChoice {
  value: ImageGenerationSize;
  label: string;
}

export interface ImageQualityChoice {
  value: ImageGenerationQuality;
  label: string;
}

export interface ImageOutputFormatChoice {
  value: ImageGenerationOutputFormat;
  label: string;
}

export const IMAGE_SIZE_OPTIONS: ImageSizeChoice[] = [
  { value: "1024x1024", label: "1024x1024" },
  { value: "1536x1024", label: "1536x1024" },
  { value: "1024x1536", label: "1024x1536" },
  { value: "auto", label: "auto" },
];

export const IMAGE_QUALITY_OPTIONS: ImageQualityChoice[] = [
  { value: "auto", label: "auto" },
  { value: "low", label: "low" },
  { value: "medium", label: "medium" },
  { value: "high", label: "high" },
];

export const IMAGE_OUTPUT_FORMAT_OPTIONS: ImageOutputFormatChoice[] = [
  { value: "png", label: "png" },
  { value: "jpeg", label: "jpeg" },
  { value: "webp", label: "webp" },
];

export function imageSizeChoiceForValue(value: string): ImageSizeChoice {
  return IMAGE_SIZE_OPTIONS.find((item) => item.value === value) ?? IMAGE_SIZE_OPTIONS[0];
}

export function imageQualityChoiceForValue(value: string): ImageQualityChoice {
  return IMAGE_QUALITY_OPTIONS.find((item) => item.value === value) ?? IMAGE_QUALITY_OPTIONS[0];
}

export function imageOutputFormatChoiceForValue(value: string): ImageOutputFormatChoice {
  return IMAGE_OUTPUT_FORMAT_OPTIONS.find((item) => item.value === value) ?? IMAGE_OUTPUT_FORMAT_OPTIONS[0];
}

export function resolveImageGenerationSize(value: string): ImageGenerationSize {
  return imageSizeChoiceForValue(value).value;
}

export function resolveImageGenerationQuality(value: string): ImageGenerationQuality {
  return imageQualityChoiceForValue(value).value;
}

export function resolveImageGenerationOutputFormat(value: string): ImageGenerationOutputFormat {
  return imageOutputFormatChoiceForValue(value).value;
}
