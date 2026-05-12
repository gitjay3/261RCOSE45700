import { expect, test } from '@playwright/test';

test.describe('Dashboard journey', () => {
  test('loads and shows today summary', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Tracker/);
    await expect(page.getByRole('heading', { name: '오늘의 탐지 현황' })).toBeVisible();
    await expect(page.getByText('Today\'s detections')).toBeVisible();
  });

  test('navigates via keyboard chord g+l', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('text=오늘의 탐지 현황');
    await page.keyboard.press('g');
    await page.keyboard.press('l');
    await expect(page).toHaveURL(/\/detections$/);
    await expect(page.getByRole('heading', { name: '탐지 목록' })).toBeVisible();
  });

  test('filters detection list by site', async ({ page }) => {
    await page.goto('/detections');
    await page.waitForSelector('table');
    const totalBefore = await page.getByText(/건$/).first().textContent();
    await page.getByRole('combobox').filter({ hasText: '사이트' }).click();
    await page.getByRole('option', { name: 'tailstar' }).click();
    await expect(page).toHaveURL(/site=tailstar/);
    const totalAfter = await page.getByText(/필터 적용:/).textContent();
    expect(totalAfter).not.toBeNull();
    expect(totalAfter).not.toBe(totalBefore);
  });

  test('opens shortcuts cheatsheet on ?', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('text=오늘의 탐지 현황');
    // useShortcut이 event.key === '?' 를 listen — Playwright는 character로 직접 dispatch 가능.
    await page.evaluate(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: '?', bubbles: true }));
    });
    await expect(page.getByRole('dialog', { name: '키보드 단축키' })).toBeVisible();
    await expect(page.getByRole('dialog')).toContainText('대시보드');
    await expect(page.getByRole('dialog')).toContainText('수동 크롤링');
  });

  test('manual trigger surfaces NewDetectionsBadge', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('text=오늘의 탐지 현황');
    await page.getByRole('button', { name: /수동 크롤링/ }).click();
    await expect(page.getByRole('dialog', { name: '지금 크롤링하시겠습니까?' })).toBeVisible();
    await page.getByRole('button', { name: '실행' }).click();
    // since=triggered 응답이 도착하면 Topbar에 "N건 새로 들어옴" 배지 등장.
    await expect(page.getByText(/건 새로 들어옴$/)).toBeVisible({ timeout: 10_000 });
  });
});
