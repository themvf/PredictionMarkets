"use server";

import { revalidatePath } from "next/cache";
import { addToWatchlist, removeFromWatchlist } from "@/db/queries/traders";

export async function toggleWatchlistAction(traderId: number, isWatched: boolean) {
  if (isWatched) {
    await removeFromWatchlist(traderId);
  } else {
    await addToWatchlist(traderId);
  }
  revalidatePath("/leaderboard");
  revalidatePath("/watchlist");
  revalidatePath("/traders");
}
