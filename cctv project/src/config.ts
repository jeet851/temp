/**
 * VisionGuard Frontend Configuration
 * 
 * Toggle between fully browser-simulated mock data and the live FastAPI backend.
 * 
 * - true  : Runs the app completely in-browser without requiring the backend server.
 * - false : Connects to the active FastAPI backend on http://localhost:8000 for live OCR telemetry.
 */
export const USE_MOCK = false;
