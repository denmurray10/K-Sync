# K-Sync UX Rules

## Freshness

- Last reviewed: 2026-04-07
- Current truth: These rules reflect the current product shape and should guide future UX decisions across public, member, and operator features.
- Legacy context: Some older pages may still have weaker CTA structure or rougher interaction handling than the target standard described here.

## Purpose

Use this guide when making UX decisions so new features feel more intentional,
consistent, and easier to use.

## CTA Hierarchy

- every screen should have one obvious primary action
- secondary actions should support, not compete with, the primary path
- tertiary actions should be visually quieter
- avoid screens where every button looks equally important

## Information Hierarchy

- show the main task first
- keep support text concise and helpful
- let typography and spacing drive hierarchy before adding extra decoration
- dense screens should still have clear grouping and scanning order

## Forms

- ask only for what the step actually needs
- show validation near the field, not only at the top
- use direct language for errors
- make success and next-step states obvious

## Loading, Empty, And Error States

- loading states should preserve layout stability
- empty states should explain what is missing and what to do next
- errors should be specific enough to recover from
- operator flows should surface failure details more directly than public-facing screens

## Navigation And Wayfinding

- users should always know where they are and what section they are in
- route or tab changes should keep context visible
- breadcrumbs or small path labels help on deeper pages
- manager tools should make the current workspace mode obvious

## Modals Versus Drawers Versus Inline Panels

- use modals for short, high-focus tasks
- use drawers when background context still matters
- use inline panels for workflows that benefit from side-by-side review or editing

## Public Versus Operator UX

### Public-facing UX

- emphasize inspiration, discovery, and momentum
- keep the path to listening, signup, or content consumption clear
- let the page feel expressive without becoming noisy

### Operator UX

- optimize for speed, error prevention, and scan efficiency
- expose status, save state, and destructive actions clearly
- reduce ambiguity in tools that mutate playlists, schedules, uploads, or publishing state

## Accessibility Basics

- maintain high contrast on dark surfaces
- keep tap targets comfortable on mobile
- never rely on color alone to communicate state
- respect reduced-motion preferences

## NotebookLM Rules

- If a feature proposal has unclear hierarchy or too many equal-weight actions, call that out.
- If a tool flow can cause destructive changes, bias toward explicit status and confirmation patterns.
- If a public page feels too dense or operational, simplify it back toward discovery and fan engagement.
