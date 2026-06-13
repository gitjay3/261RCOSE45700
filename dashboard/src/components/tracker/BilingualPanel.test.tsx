import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { BilingualPanel } from './BilingualPanel';

describe('BilingualPanel', () => {
  it('shows the translation panel when translatedText exists even if language is ko', () => {
    render(
      <BilingualPanel
        originalText="月外掛最新版本上傳。免費"
        originalLang="ko"
        translatedText="월 외부 핵 최신 버전 업로드. 무료."
      />,
    );

    expect(screen.getByLabelText('원문과 번역')).toBeInTheDocument();
    expect(screen.getByText('번역 (한국어)')).toBeInTheDocument();
    expect(screen.getByText('월 외부 핵 최신 버전 업로드. 무료.')).toBeInTheDocument();
  });

  it('shows a single original panel when translatedText is empty', () => {
    render(
      <BilingualPanel
        originalText="정상 게임 공략입니다."
        originalLang="ko"
        translatedText={null}
      />,
    );

    expect(screen.getByLabelText('원문')).toBeInTheDocument();
    expect(screen.queryByText('번역 (한국어)')).not.toBeInTheDocument();
  });
});
