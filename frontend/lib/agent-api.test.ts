import { describe, expect, it } from "vitest";

import { parseSseBuffer } from "./agent-api";

describe("parseSseBuffer", () => {
  it("keeps partial blocks and parses complete events", () => {
    const first = parseSseBuffer('event: delta\ndata: {"text":"hel"}\n\nevent: del');
    expect(first.events).toEqual([{ event: "delta", payload: { text: "hel" } }]);
    expect(first.remainder).toBe("event: del");
  });

  it("supports CRLF and multiline data", () => {
    const parsed = parseSseBuffer('event: complete\r\ndata: {"ok":\r\ndata: true}\r\n\r\n', true);
    expect(parsed.events).toEqual([{ event: "complete", payload: { ok: true } }]);
  });
});
