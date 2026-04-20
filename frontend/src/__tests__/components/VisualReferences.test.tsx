import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VisualReferences } from "../../components/VisualReferences";
import { projectsApi } from "../../api/client";
import { renderWithProviders } from "../test-utils";

vi.mock("../../api/client", async (orig) => {
  const m = await orig<typeof import("../../api/client")>();
  return {
    ...m,
    projectsApi: {
      ...m.projectsApi,
      uploadVisualReference: vi.fn(),
    },
  };
});

describe("VisualReferences", () => {
  const uploadVisualReference = vi.mocked(projectsApi.uploadVisualReference);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("adds a URL reference", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(<VisualReferences references={[]} onChange={onChange} />);
    await user.click(screen.getAllByRole("button", { name: /add url/i })[0]);
    await user.type(
      screen.getByPlaceholderText("https://example.com/mockup.png"),
      "https://example.com/a.png"
    );
    await user.click(screen.getAllByRole("button", { name: /add url/i })[1]);
    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({
        type: "url",
        url: "https://example.com/a.png",
      }),
    ]);
  });

  it("uploads an image file on success", async () => {
    uploadVisualReference.mockResolvedValue({
      file_name: "a.png",
      s3_key: "k",
      description: "",
      preview_url: "https://x",
    });
    const user = userEvent.setup();
    const onChange = vi.fn();
    const file = new File(["x"], "a.png", { type: "image/png" });
    renderWithProviders(<VisualReferences references={[]} onChange={onChange} />);
    const input = document.getElementById("visual-upload") as HTMLInputElement;
    await user.upload(input, file);
    await waitFor(() => {
      expect(uploadVisualReference).toHaveBeenCalled();
    });
    expect(onChange).toHaveBeenCalled();
  });
});
