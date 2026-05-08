export type PetSignalType = "send" | "complete" | "error";

export type PetSignal = {
  id: number;
  type: PetSignalType;
};
