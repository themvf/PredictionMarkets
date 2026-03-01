/**
 * Neon PostgreSQL connection via HTTP (serverless-friendly).
 *
 * Uses @neondatabase/serverless under the hood — each query is a
 * stateless HTTP request, perfect for Vercel serverless functions.
 * No connection pooling or TCP sockets needed.
 */

import { neon } from "@neondatabase/serverless";
import { drizzle } from "drizzle-orm/neon-http";
import * as schema from "./schema";

if (!process.env.DATABASE_URL) {
  throw new Error(
    "DATABASE_URL is not set. " +
    "Add it to .env.local for local development or to Vercel Environment Variables for production."
  );
}

const sql = neon(process.env.DATABASE_URL);

export const db = drizzle({ client: sql, schema });
