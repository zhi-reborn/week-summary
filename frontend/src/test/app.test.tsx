import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "../app";

describe("App", () => {
  it("shows the product title and create action", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "智能周报汇总系统" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "新建周报汇总" })).toBeInTheDocument();
  });
});
