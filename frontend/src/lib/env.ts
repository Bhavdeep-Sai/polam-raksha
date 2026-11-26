import { z } from "zod";

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().url().default("http://localhost:8000"),
  VITE_WS_BASE_URL: z.string().min(1).default("ws://localhost:8000"),
  VITE_DEFAULT_LOCALE: z.enum(["en", "te"]).default("te"),
});

const parsed = envSchema.safeParse({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  VITE_WS_BASE_URL: import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000",
  VITE_DEFAULT_LOCALE: import.meta.env.VITE_DEFAULT_LOCALE || "te",
});

if (!parsed.success) {
  throw new Error(`Invalid frontend environment configuration: ${parsed.error.message}`);
}

export const env = parsed.data;

