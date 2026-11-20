import type { AnalyseResponse } from "@/types";

// Preview images and processing notes live only in memory for the current upload
// session. They are never persisted, so a page refresh drops them on purpose.
const store = new Map<number, AnalyseResponse>();

export const analysisStore = {
  set(result: AnalyseResponse) {
    store.set(result.prescription.id, result);
  },
  get(prescriptionId: number): AnalyseResponse | undefined {
    return store.get(prescriptionId);
  },
  clear(prescriptionId: number) {
    store.delete(prescriptionId);
  },
};
