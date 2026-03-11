# UI Refactor Plan

## 1. Context

The current Tauri frontend is functionally effective but structurally constrained.

- Most frontend logic, state, event handling, and layout rendering currently live in `src/App.tsx`.
- Most UI styling is centralized in `src/styles.css`.
- The current interface has weak hierarchy and a relatively flat layout, with too many controls and information blocks competing at the same visual level.
- Business logic and layout are tightly coupled, which makes structural UI changes riskier than necessary.

This coupling is visible in several areas:

- Translation state, backend readiness, progress streaming, clipboard integration, OCR actions, hotkey integration, and layout markup are managed together in the same component.
- The current UI is effectively a single-page workspace with limited architectural separation between navigation, page structure, and contextual information.
- Presentation concerns are mixed with business concerns, which makes incremental layout evolution harder to do safely.

The goal of this refactor is to introduce a stable App Shell architecture while preserving the existing translation functionality and minimizing regression risk. The initial work is a structural refactor, not a redesign of translation behavior or backend integration.

Core objective:

- Establish a durable UI architecture that can support clearer hierarchy, better grouping, and future growth without disrupting the current translation flow.

## 2. Target UI Architecture

This refactor targets a structural UI architecture with clear responsibility boundaries. The emphasis is on layout logic, navigation discipline, and progressive disclosure rather than visual styling.

### Information Architecture

The target information architecture is organized into four layers:

- Global layer: application-wide capabilities such as workspace context, global search/command entry, settings access, and account-level controls.
- Module layer: top-level product areas such as Home, Work, History, Resources, and Settings.
- Page layer: the active screen within a module, with a stable page template and a single primary task focus.
- Context layer: supplementary information related to the current object or task, such as progress details, metadata, history, validation, or diagnostics.

This separation is intended to stop unrelated concerns from appearing at the same visual level. The user should always be able to distinguish:

- where they are in the app,
- what they are currently doing,
- what information is primary,
- what information is contextual and optional.

### App Shell Layout

The target shell is a stable application frame composed of:

- Sidebar: persistent module-level navigation.
- Main Workspace: the primary task area for the active page.
- Context Panel: a collapsible secondary area for selected-object or task-specific supporting information.
- Top Bar: global controls and lightweight app-level status.
- Status Bar: background state, progress, sync, or operational feedback.

The shell should establish a durable spatial model:

- Sidebar answers "where to go."
- Main Workspace answers "what the user is doing now."
- Context Panel answers "what additional information is relevant to the current task."
- Top Bar and Status Bar provide stable global framing without becoming overloaded with page-specific controls.

### Navigation Model

The proposed primary module structure is:

- Home
- Work
- History
- Resources
- Settings

These modules are organizational anchors, not merely visual tabs. They should reflect major user intents rather than an arbitrary collection of controls.

Navigation rules:

- Sidebar owns primary module navigation.
- Page-local navigation should remain inside the active page, not inside the global sidebar.
- Contextual object details should not appear as navigation items.
- The navigation model should stay stable across most screens to improve predictability and spatial memory.

### Page Layout Template

Each major page should follow a consistent structural template:

- `PageHeader`: page title, current object title if applicable, and page-level primary actions.
- `LocalToolbar`: page-specific controls such as search, filtering, sorting, mode switching, or view switching.
- `PrimaryContent`: the main work surface for the page. There should only be one primary content focus.
- `ContextArea`: optional secondary area for supporting task or object information.
- `StatusLayer`: non-primary operational feedback such as progress, sync state, warnings, or background task feedback.

This template is designed to ensure that control density stays disciplined and that supporting information does not compete with the page's main work surface.

### Component Grouping System

The proposed grouping model is semantic, not decorative. Components should be grouped by interaction role:

- `NavigationGroup`: global or section-level navigation.
- `Section`: a major task area within a page.
- `Panel`: a grouped set of related controls or information.
- `Collection`: lists, feeds, search results, or resource collections.
- `Inspector`: current-object properties, metadata, or contextual details.
- `ActionCluster`: a small group of related actions tied to the same object or task.
- `FeedbackBlock`: errors, success messages, progress states, warnings, or background process messages.

The purpose of this system is to prevent random container usage and to make future page layouts easier to reason about.

### Progressive Disclosure Strategy

The target disclosure model uses four visibility levels:

- Level 0: always-visible structural anchors such as the shell, primary navigation, and essential global controls.
- Level 1: page-default content required to perform the primary task.
- Level 2: context-dependent content revealed after selection, deeper task entry, or explicit user action.
- Level 3: advanced or low-frequency controls such as diagnostics, advanced settings, bulk actions, or secondary tooling.

The goal is to reduce default clutter while preserving access to advanced functionality when needed. Secondary information should appear because of state, intent, or explicit user request, not because it happens to exist.

## 3. Refactor Strategy

The key principle of this refactor is containment of change.

During the early stages, `App.tsx` should remain the container component. This means:

- business logic stays in `App.tsx`,
- translation state stays in `App.tsx`,
- API calls stay in `App.tsx`,
- translation flow and streaming orchestration stay in `App.tsx`,
- hotkey integration stays in `App.tsx`,
- backend readiness logic stays in `App.tsx`.

This is intentional. The first phase of work is about stabilizing layout structure, not redistributing core behavior.

The refactor should therefore focus on extracting layout and presentation components while leaving application behavior intact. In practice:

- layout markup can be moved into shell and page components,
- visual sections can be split into presentation components,
- props can be passed down from `App.tsx`,
- business logic should only move after the layout architecture is stable and verified.

This approach reduces regression risk and makes each refactor step easier to validate.

## 4. Incremental Implementation Plan

### Milestone 1

Introduce App Shell layout components without changing functionality.

Scope:

- Add structural layout components such as shell, top bar, main workspace wrapper, and status region.
- Reorganize the existing JSX into a stable shell format.
- Keep the current translation experience functionally identical.
- Do not move business logic out of `App.tsx`.

Goal:

- Establish a stable outer layout with minimal behavioral risk.

### Milestone 2

Add sidebar navigation with a lightweight `activeView` state.

Scope:

- Introduce a sidebar for primary module navigation.
- Use a local view-state model such as `activeView` instead of full routing.
- Keep `Work` as the primary active screen initially.
- Use placeholder page containers for future modules if necessary.

Goal:

- Create a navigation framework without introducing routing complexity or breaking current workflows.

### Milestone 3

Split the translation UI into presentation components.

Scope:

- Extract the current translation interface into smaller presentation-focused components.
- Keep these components prop-driven and controlled by `App.tsx`.
- Separate layout concerns from translation behavior.

Goal:

- Reduce structural complexity inside `App.tsx` while preserving all current translation logic.

### Milestone 4

Introduce a collapsible context panel.

Scope:

- Add a context panel that can open and close without affecting the core work surface.
- Start by placing secondary information there, such as progress detail, segment preview, metadata, or related support content.
- Keep all primary translation actions outside the panel.

Goal:

- Create a dedicated home for secondary information without shrinking the primary work area into clutter.

### Milestone 5

Move configuration controls into a dedicated settings page.

Scope:

- Shift low-frequency or advanced configuration out of the default work surface.
- Keep only task-critical controls in the main work page.
- Use the new Settings module to absorb persistent application and backend-related configuration UI.

Goal:

- Reduce control density in the main translation workflow and improve hierarchy.

### Milestone 6

Clean up styles and establish layout class conventions.

Scope:

- Consolidate shell and page-level layout classes.
- Remove obsolete layout styles left over from the previous single-page structure.
- Introduce predictable class naming for shell regions, page regions, and context areas.

Goal:

- Make the new structure maintainable and reduce CSS drift as the UI evolves.

## 5. Proposed Component Structure

The following components are proposed as initial structural building blocks.

### Layout Components

- `AppShell`
- `TopBar`
- `Sidebar`
- `MainWorkspace`
- `ContextPanel`
- `StatusBar`

### Page-Level and Work-Surface Components

- `TranslationControls`
- `InputEditor`
- `OutputPanel`
- `TranslationProgressSummary`
- `TranslationSettingsForm`

These components should initially be presentation components receiving props from `App.tsx`.

Initial expectation:

- no business ownership,
- no independent API orchestration,
- no duplication of source-of-truth state,
- no migration of streaming logic during early milestones.

This keeps `App.tsx` as the container and allows the refactor to progress safely through structure-first extraction.

## 6. Risk Control

The refactor must preserve current translation behavior throughout the incremental rollout.

Non-negotiable constraints:

- Translation streaming must remain unchanged.
- Cancel and stop actions must continue to work.
- Clipboard translation and OCR flows must not regress.
- Hotkeys must remain functional.
- Backend readiness logic must remain intact.

Operational discipline for each milestone:

- Avoid changing translation orchestration while changing layout.
- Validate that progress updates still render correctly.
- Confirm that current actions remain reachable in the new structure.
- Keep regression scope local to the milestone being implemented.

Testing expectation:

- Each refactor step must be tested by running the desktop app.

Minimum manual verification after each milestone:

- app startup,
- backend ready state,
- standard text translation,
- streaming progress visibility,
- cancel/stop behavior,
- clipboard translation,
- OCR clipboard flow,
- hotkey-triggered translation,
- copy output behavior,
- settings persistence where relevant.

## 7. Future Work

The following items are reasonable future improvements but are not part of the current refactor scope:

- introducing routing if multiple modules grow beyond a lightweight `activeView` approach,
- defining design tokens or a more formal component library,
- adding stronger responsive rules for smaller window sizes and narrow desktop layouts.

These items should be considered only after the new shell, page template, and component extraction strategy are stable.
