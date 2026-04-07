# K-Sync Component Patterns

## Freshness

- Last reviewed: 2026-04-07
- Current truth: These patterns reflect recurring component behavior across homepage, live, signup, dashboard, and playlist manager surfaces.
- Legacy context: Some older pages may only partially follow these patterns, especially prototype or exported lab routes.

## Purpose

Use this guide when designing components so future UI work stays visually and
behaviorally consistent.

## Buttons

### Primary action buttons

- default to pink fill or cyan fill depending on context
- use uppercase, bold labels
- keep corners square
- use strong hover inversion or offset shadow motion
- labels should be short and decisive

### Secondary buttons

- border-first styling on dark surfaces
- lighter hierarchy than primary actions
- use white, slate, or cyan depending on emphasis

### Destructive buttons

- reserve red for destructive or dangerous actions
- do not let destructive styling compete with core pink CTA hierarchy

## Inputs And Forms

- dark inputs with crisp borders
- icon-led inputs are acceptable when they improve scan speed
- placeholder text should be muted but readable
- validation should be direct, visible, and specific
- form labels should use small uppercase utility styling

## Cards And Panels

- default panels should be black, near-black, or glass-dark
- use borders and spacing to separate content
- avoid soft white SaaS cards as the default
- stat cards should use strong numeric hierarchy and restrained chrome

## Status Chips And Badges

- use pill shapes sparingly and intentionally
- good uses: live, new, queued, premium, tier, status
- keep badges small, high-contrast, and uppercase

## Lists, Tables, And Catalogues

- dense lists should still preserve hierarchy between title, metadata, and actions
- use mono or tight uppercase labels for utility metadata
- hover and selection states should be clear without flooding the UI with color
- keep drag handles, destructive actions, and row status visually distinct

## Drawers, Modals, And Overlays

- use modals for short, focused tasks or high-attention moments
- use drawers or side panels for contextual editing where background state matters
- operator flows should prefer fast, structured overlays over decorative popups

## Navigation

- desktop navigation should feel ceremonial and precise
- active state should use more than color alone
- internal tool tabs should feel like control-deck navigation, not casual tabs

## Hero Blocks

- heroes should combine one dramatic headline, one clear support line, and one strong primary action
- use imagery, glow, and spacing carefully
- avoid overloading the first viewport with too many competing modules

## Empty States

- keep empty states useful and encouraging, not jokey
- explain what is missing and what the next action should be
- public empty states can be more atmospheric
- operator empty states should prioritize clarity and next-step action

## NotebookLM Rules

- Prefer K-Beats component patterns over generic Tailwind defaults.
- If a page needs a new component, infer it from existing button, panel, form, or list behavior before inventing a new visual language.
- Operator components should stay dense and sharp-edged; public components should carry more broadcast energy.
