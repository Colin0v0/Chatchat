import { apiFetch } from "../../../shared/api/http";

export type PetStatePosition = {
  bottom: number;
  left: number;
};

export type PetStateStats = {
  energy: number;
  hunger: number;
  mood: number;
  thirst: number;
};

export type PetStateApiResponse = {
  sleeping: boolean;
  position: PetStatePosition;
  stats: PetStateStats;
  updatedAt: number;
};

export type PetStateApiUpdate = {
  sleeping: boolean;
  position: PetStatePosition;
  stats: PetStateStats;
};

export async function fetchPetState(): Promise<PetStateApiResponse> {
  return apiFetch<PetStateApiResponse>("/api/pet/state");
}

export async function savePetState(payload: PetStateApiUpdate): Promise<PetStateApiResponse> {
  return apiFetch<PetStateApiResponse>("/api/pet/state", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
