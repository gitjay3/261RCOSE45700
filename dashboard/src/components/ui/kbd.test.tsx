import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Kbd } from './kbd';

describe('Kbd', () => {
  it('renders children with data-slot for tooltip selector compatibility', () => {
    render(<Kbd>g</Kbd>);
    const el = screen.getByText('g');
    expect(el).toBeInTheDocument();
    expect(el.tagName).toBe('KBD');
    expect(el).toHaveAttribute('data-slot', 'kbd');
  });

  it('applies inverse variant class', () => {
    render(<Kbd variant="inverse">o</Kbd>);
    expect(screen.getByText('o')).toHaveClass('bg-primary-foreground/15');
  });

  it('applies outline variant + min-width on md size', () => {
    render(
      <Kbd variant="outline" size="md">
        Enter
      </Kbd>,
    );
    const el = screen.getByText('Enter');
    expect(el).toHaveClass('border');
    expect(el).toHaveClass('min-w-[24px]');
  });

  it('merges custom className with variant classes', () => {
    render(<Kbd className="ml-4">x</Kbd>);
    const el = screen.getByText('x');
    expect(el).toHaveClass('ml-4');
    expect(el).toHaveClass('bg-muted');
  });
});
