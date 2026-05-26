import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

describe("API Client", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("getPublicItems should call correct endpoint", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    const { getPublicItems } = await import("@/lib/api");
    const result = await getPublicItems();

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/public/items"),
      expect.anything(),
    );
    expect(result).toEqual([]);
  });

  it("should throw on API error", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Not found" }),
    });

    const { getPublicItems } = await import("@/lib/api");
    await expect(getPublicItems()).rejects.toThrow("Not found");
  });

  it("login should call auth endpoint", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: "Login successful" }),
    });

    const { login } = await import("@/lib/api");
    const result = await login("admin", "password");

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/auth/login"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.message).toBe("Login successful");
  });
});
