import { expect, test } from '@playwright/test';

test.describe('Mobile viewport (Pixel 7)', () => {
  test('Dashboard loads + hamburger toggles Sidebar drawer', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: '오늘의 탐지 현황' })).toBeVisible();

    // 햄버거 버튼은 < lg 에서만 노출
    const hamburger = page.getByRole('button', { name: '메뉴 열기' });
    await expect(hamburger).toBeVisible();

    await hamburger.click();
    // <aside aria-label="주 탐색"> 의 implicit role은 complementary. accessible name으로 한정.
    const drawer = page.getByLabel('주 탐색');
    await expect(drawer.getByRole('link', { name: '탐지 목록' })).toBeVisible();

    // 라우트 전환 시 drawer 자동 닫힘 — translate-x-full 로 viewport 밖 이동.
    await drawer.getByRole('link', { name: '탐지 목록' }).click();
    await expect(page).toHaveURL(/\/detections$/);
    await expect(drawer).not.toBeInViewport();
  });

  test('DetectionList renders mobile cards (no horizontal table overflow)', async ({ page }) => {
    await page.goto('/detections');
    await page.waitForSelector('text=탐지 목록');

    // table은 < md에서 hidden — 카드만 보임
    const table = page.locator('table');
    await expect(table).toBeHidden();

    // 카드 클릭 시 detail 이동
    const firstCard = page.getByRole('button', { name: /탐지 상세 열기/ }).first();
    await expect(firstCard).toBeVisible();
    await firstCard.click();
    await expect(page).toHaveURL(/\/detections\/\d+$/);
  });

  test('FilterBar opens bottom Drawer with full filter panel', async ({ page }) => {
    await page.goto('/detections');
    await page.waitForSelector('text=탐지 목록');

    await page.getByRole('button', { name: /^필터$/ }).click();
    const dialog = page.getByRole('dialog', { name: '필터' });
    await expect(dialog).toBeVisible();
    // 3 select labels — dialog scope에 한정해 DesktopFilterBar의 hidden duplicate 회피
    await expect(dialog.getByText('사이트', { exact: true })).toBeVisible();
    await expect(dialog.getByText('유형', { exact: true })).toBeVisible();
    await expect(dialog.getByText('언어', { exact: true })).toBeVisible();

    // 완료로 닫기
    await dialog.getByRole('button', { name: '완료' }).click();
    await expect(dialog).not.toBeVisible();
  });

  test('shortcut hints hidden on mobile', async ({ page }) => {
    await page.goto('/detections');
    // 데스크탑 풋터 힌트 "팁: j/k Enter ? 전체 단축키"는 hidden md:block
    const hint = page.getByText(/팁:.*전체 단축키/);
    await expect(hint).toBeHidden();
  });
});
