import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = "/Users/nohgiyoon/Coding/AI/Agent/frontend";

function read(relativePath) {
  return readFileSync(join(root, relativePath), "utf8");
}

function expectIncludes(source, expected, message) {
  assert.ok(source.includes(expected), message);
}

test("connections page exports default function with expected title and back link", () => {
  const source = read("src/app/setup/connections/page.tsx");
  expectIncludes(source, "export default function SetupConnectionsPage()", "missing default export");
  expectIncludes(source, 't("setup_connections_title", "외부 서비스 연결")', "missing connections title");
  expectIncludes(source, 'href="/setup"', "missing setup back link");
  expectIncludes(
    source,
    't("setup_back_to_settings", "← 설정으로 돌아가기")',
    "missing translated back label"
  );
});

test("permissions page exports default function with expected title and back link", () => {
  const source = read("src/app/setup/permissions/page.tsx");
  expectIncludes(source, "export default function SetupPermissionsPage()", "missing default export");
  expectIncludes(source, 't("setup_permissions_title", "권한 관리")', "missing permissions title");
  expectIncludes(source, 'href="/setup"', "missing setup back link");
  expectIncludes(
    source,
    't("setup_back_to_settings", "← 설정으로 돌아가기")',
    "missing translated back label"
  );
});

test("tools page exports default function with expected title and back link", () => {
  const source = read("src/app/setup/tools/page.tsx");
  expectIncludes(source, "export default function SetupToolsPage()", "missing default export");
  expectIncludes(source, 't("setup_tools_title", "도구 설정")', "missing tools title");
  expectIncludes(source, 'href="/setup"', "missing setup back link");
  expectIncludes(
    source,
    't("setup_back_to_settings", "← 설정으로 돌아가기")',
    "missing translated back label"
  );
});

test("LanguageProvider includes ko/en keys for setup subpages", () => {
  const source = read("src/components/LanguageProvider.tsx");
  for (const expected of [
    'setup_back_to_settings: "← 설정으로 돌아가기"',
    'setup_connections_title: "외부 서비스 연결"',
    'setup_permissions_title: "권한 관리"',
    'setup_tools_title: "도구 설정"',
    'setup_back_to_settings: "← Back to setup"',
    'setup_connections_title: "External Service Connections"',
    'setup_permissions_title: "Permission Management"',
    'setup_tools_title: "Tool Settings"',
  ]) {
    expectIncludes(source, expected, `missing translation key: ${expected}`);
  }
});
