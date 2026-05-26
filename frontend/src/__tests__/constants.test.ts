import { describe, it, expect } from "vitest";
import { SITE_NAME, SITE_DESCRIPTION } from "@/lib/constants";

describe("Constants", () => {
  it("should have site name", () => {
    expect(SITE_NAME).toBe("MyApp");
  });

  it("should have site description", () => {
    expect(SITE_DESCRIPTION).toBeDefined();
    expect(SITE_DESCRIPTION.length).toBeGreaterThan(0);
  });
});
