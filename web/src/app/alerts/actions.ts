"use server";

import { revalidatePath } from "next/cache";
import { acknowledgeAlert } from "@/db/queries/alerts";

export async function acknowledgeAlertAction(alertId: number) {
  await acknowledgeAlert(alertId);
  revalidatePath("/alerts");
}
