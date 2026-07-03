---
version: alpha
name: Classroom Support Console
description: Minimal DESIGN.md adapted from google-labs-code/design.md for a Google Classroom operations support prototype.
references:
  - https://github.com/ChiOtter/design.md_google-labs-code
  - https://github.com/google-labs-code/design.md
colors:
  primary: "#1A73E8"
  primary-strong: "#185ABC"
  background: "#F8FAFD"
  surface: "#FFFFFF"
  surface-muted: "#F1F3F4"
  text: "#202124"
  text-muted: "#5F6368"
  line: "#DADCE0"
  success: "#188038"
  warning: "#A05A00"
  danger: "#B3261E"
typography:
  heading-lg:
    fontFamily: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
    fontSize: 22px
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: 0
  heading-md:
    fontFamily: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
    fontSize: 18px
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: 0
  body-md:
    fontFamily: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: 0
  label-sm:
    fontFamily: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
    fontSize: 13px
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: 0
rounded:
  sm: 4px
  md: 8px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 28px
  page: 28px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
    height: 40px
    padding: 14px
  button-primary-hover:
    backgroundColor: "{colors.primary-strong}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: 18px
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    height: 42px
  sidebar-active:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
  table:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
  divider:
    backgroundColor: "{colors.line}"
    height: 1px
  badge-success:
    backgroundColor: "#ECFDF3"
    textColor: "{colors.success}"
    rounded: "{rounded.full}"
  alert-warning:
    backgroundColor: "#FFFBEB"
    textColor: "{colors.warning}"
    rounded: "{rounded.md}"
  alert-danger:
    backgroundColor: "#FFF4F2"
    textColor: "{colors.danger}"
    rounded: "{rounded.md}"
  metadata:
    textColor: "{colors.text-muted}"
---

## Overview

This file intentionally uses only the small, useful part of `google-labs-code/design.md`: machine-readable YAML tokens plus short human-readable design rationale. The original format says that "the tokens are the normative values"; this project follows that idea by keeping exact color, type, spacing, radius, and component values in front matter, then explaining the application rules below.

This product is a teacher-facing operations console for Google Classroom. The UI should feel calm, practical, and trustworthy rather than decorative. It supports repeated classroom administration tasks: checking submissions, reviewing AI-generated drafts, editing text, choosing outputs, and approving Classroom posts.

The visual direction follows Google-adjacent product conventions: bright surfaces, clear hierarchy, blue primary actions, semantic status colors, compact cards, and data-first tables. The design should make the teacher feel in control, especially when AI output may affect students. The example themes in the source repository are treated as references for structure, not as visual styles to copy.

## Colors

- **Primary blue (`#1A73E8`)** is used for the main action path: login, open course, generate reminder, proceed, and approve.
- **Background (`#F8FAFD`)** keeps the workspace light without using pure white for the whole page.
- **Surface (`#FFFFFF`)** is used for cards, panels, forms, tables, and dialogs.
- **Muted surface (`#F1F3F4`)** is used for active navigation and low-emphasis controls.
- **Text (`#202124`)** is the default foreground color.
- **Muted text (`#5F6368`)** is used for metadata, secondary explanations, and timestamps.
- **Line (`#DADCE0`)** is used for borders and table dividers.
- **Success, warning (`#A05A00`), and danger (`#B3261E`)** are reserved for submission status, partial data warnings, validation errors, and approval risk. Warning and danger text use darker tones so alerts remain readable on pale backgrounds.

## Typography

Use the system UI font stack to stay close to Google product ergonomics and avoid extra font loading. Text should be compact and readable. Do not use oversized marketing-style headings inside the app. Dashboard headings, table labels, buttons, form labels, and warning messages should support quick scanning.

## Layout

Use a two-column app shell on desktop: a fixed left sidebar and a main content area. The main content width should remain constrained enough for tables and form review to stay readable. Use a single-column layout on small screens.

The primary workflow is:

1. Login
2. Course selection
3. Dashboard
4. Assignment detail
5. AI output review
6. Output selection
7. Posting confirmation

## Elevation & Depth

Use subtle shadows only for cards and important panels. Most hierarchy should come from spacing, borders, headings, and semantic color. Avoid heavy shadows, gradients, decorative backgrounds, and large hero sections.

## Shapes

Use `8px` radius for cards, buttons, inputs, panels, and table containers. Use pill shapes only for small status badges. The interface should feel orderly and operational, not playful.

## Components

- **Sidebar navigation:** persistent app sections with the active item shown by muted surface fill.
- **Top bar:** page title, current course context, and account action.
- **Metric cards:** compact summary numbers for missing submissions, approaching deadlines, late submissions, and recent notices.
- **Tables:** primary structure for coursework and submission status. Tables should support horizontal overflow on small screens.
- **Alerts and warnings:** use semantic colors and concise text. Warnings about posting and student privacy must be visible before approval.
- **Editable fields:** AI-generated text must be editable before posting or exporting.
- **Approval actions:** Classroom posting must use a primary action only after validation succeeds.

## Do's and Don'ts

- Do keep the interface dense enough for teachers to compare courses, assignments, and submission status quickly.
- Do show loading, empty, partial-success, and error states.
- Do separate factual Classroom data from AI-generated recommendations.
- Do require explicit teacher approval before Classroom posting.
- Do not include individual missing student names in student-facing posts.
- Do not use decorative illustrations, oversized hero sections, or promotional copy.
- Do not introduce a one-note blue interface; keep semantic success, warning, and danger colors distinct.
- Do not make AI output read-only when it may be posted or exported.
