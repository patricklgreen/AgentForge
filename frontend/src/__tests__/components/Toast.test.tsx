import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastContainer, useToast, type Toast } from "../../components/Toast";

describe("Toast", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders toast with message and dismisses manually", async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    const toast: Toast = {
      id: "1",
      type: "success",
      title: "Saved",
      message: "Done",
      duration: 60_000,
    };
    render(<ToastContainer toasts={[toast]} onDismiss={onDismiss} />);
    expect(screen.getByText("Saved")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /dismiss/i }));
    await waitFor(() => expect(onDismiss).toHaveBeenCalledWith("1"));
  });

  it("useToast adds a toast via success()", async () => {
    const user = userEvent.setup();
    function Harness() {
      const { success, ToastContainer: TC } = useToast();
      return (
        <div>
          <button type="button" onClick={() => success("Hi", "There", 5000)}>
            go
          </button>
          <TC />
        </div>
      );
    }
    render(<Harness />);
    await user.click(screen.getByText("go"));
    expect(await screen.findByText("Hi")).toBeInTheDocument();
    expect(screen.getByText("There")).toBeInTheDocument();
  });

  it("dismissToast removes a toast from useToast state", async () => {
    const user = userEvent.setup();
    function Harness() {
      const { success, dismissToast, toasts, ToastContainer: TC } = useToast();
      return (
        <div>
          <button type="button" onClick={() => success("X", undefined, 60000)}>
            add
          </button>
          <button
            type="button"
            onClick={() => {
              const id = toasts[0]?.id;
              if (id) dismissToast(id);
            }}
          >
            rm
          </button>
          <TC />
        </div>
      );
    }
    render(<Harness />);
    await user.click(screen.getByText("add"));
    expect(await screen.findByText("X")).toBeInTheDocument();
    await user.click(screen.getByText("rm"));
    await waitFor(() => expect(screen.queryByText("X")).not.toBeInTheDocument());
  });
});
