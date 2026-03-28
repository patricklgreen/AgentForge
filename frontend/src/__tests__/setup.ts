import "@testing-library/jest-dom";
import { vi } from "vitest";

// Mock Monaco Editor — it requires a DOM environment not available in jsdom
vi.mock("@monaco-editor/react", () => ({
  default: vi.fn(({ value }: { value: string }) => (
    <div data-testid="monaco-editor" data-value={value?.substring(0, 100)}>
      {/* Monaco Editor Mock */}
    </div>
  )),
}));

// Mock environment variables
vi.stubEnv("VITE_API_URL", "http://localhost:8000");
vi.stubEnv("VITE_WS_URL",  "ws://localhost:8000");

// Silence console.error noise in tests (e.g. React act() warnings)
const originalError = console.error.bind(console);
beforeAll(() => {
  console.error = (...args: unknown[]) => {
    if (
      typeof args[0] === "string" &&
      (args[0].includes("Warning: ReactDOM.render") ||
        args[0].includes("act("))
    ) {
      return;
    }
    originalError(...args);
  };
});
afterAll(() => {
  console.error = originalError;
});
