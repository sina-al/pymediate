# Documentation Checklist

**Use this checklist for EVERY feature, change, or enhancement.**

## ✅ Before Starting Implementation

- [ ] Understand the user's pedagogical goals
- [ ] Identify all documentation touchpoints
- [ ] Plan documentation structure

## ✅ During Implementation

### Code Documentation

- [ ] **Docstrings**: Every public class/function has Google-style docstring
  - [ ] Brief one-line summary
  - [ ] Detailed explanation (what, why, when to use)
  - [ ] Args with types and descriptions
  - [ ] Returns with type and description
  - [ ] Raises with exception types
  - [ ] Examples (simple → complex progression)
  - [ ] See Also links to related functionality
  - [ ] Notes about edge cases/gotchas

- [ ] **Type Hints**: All parameters and returns fully typed
- [ ] **Comments**: Explain "why" not "what" for complex logic
- [ ] **Examples in docstrings**: Actually runnable, tested code

### README.md

- [ ] Update Quick Example if feature affects basic usage
- [ ] Add new feature to Features section
- [ ] Add usage example if feature is user-facing
- [ ] Keep examples simple and focused
- [ ] Update Installation if dependencies changed

### Getting Started Documentation

- [ ] **docs/getting-started/quick-start.md**
  - [ ] Add to step-by-step tutorial if relevant
  - [ ] Keep progression: basic → intermediate → advanced

- [ ] **docs/getting-started/concepts.md**
  - [ ] Add conceptual explanation
  - [ ] Explain "why" this concept exists
  - [ ] Show how it relates to other concepts
  - [ ] Include diagrams if helpful

### Guide Documentation

- [ ] **docs/guide/[relevant].md**
  - [ ] Comprehensive guide for the feature
  - [ ] Table of contents for long guides
  - [ ] Progressive examples (simple first!)
  - [ ] Common use cases section
  - [ ] Best practices section
  - [ ] Common pitfalls / troubleshooting
  - [ ] Integration with other features

### Examples Documentation

- [ ] **docs/examples/[feature].md**
  - [ ] 5+ complete, runnable examples
  - [ ] Cover common use cases
  - [ ] Progress from simple to complex
  - [ ] Include real-world scenarios
  - [ ] Show integration patterns

### API Reference

- [ ] **docs/api/[module].md**
  - [ ] Use mkdocstrings for auto-generation
  - [ ] Brief intro paragraph
  - [ ] Links to guides and examples
  - [ ] Organized by logical groups

## ✅ After Implementation

### Testing

- [ ] **Comprehensive tests** (isolated + integration + e2e)
- [ ] **Test coverage** ≥95% for new code
- [ ] **Mypy tests** for type safety scenarios
- [ ] **Docstring examples** are actually tested (doctest or explicit)

### Quality Checks

- [ ] `uv run poe type:all` passes (strict mypy)
- [ ] `uv run poe lint` passes (ruff)
- [ ] `uv run poe format` applied
- [ ] `uv run poe test` all pass
- [ ] `uv run poe docs:build` successful

### Final Review

- [ ] All documentation cross-links work
- [ ] Terminology is consistent across all docs
- [ ] Examples follow same structure/style
- [ ] No broken references
- [ ] Navigation in mkdocs.yml updated if needed
- [ ] CLAUDE.md updated if architecture changed

## 📋 Pedagogical Best Practices

### Order of Presentation
1. **Why** - Motivation and problem this solves
2. **What** - Concept explanation with analogy
3. **How** - Simple example
4. **When** - Use cases and decision guide
5. **Advanced** - Complex patterns and edge cases

### Example Progression
1. Minimal viable example (5-10 lines)
2. Realistic basic example (with context)
3. Production-like example (with error handling)
4. Advanced/edge case examples

### Writing Style
- Use active voice ("The mediator routes requests")
- Present tense for descriptions
- Imperative for instructions ("Add the behavior...")
- Include "why" explanations, not just "how"
- Anticipate questions readers will have

### Code Examples
- Actually runnable (copy-paste works)
- Include necessary imports
- Show complete context (not fragments)
- Use realistic names (not foo/bar)
- Add comments for non-obvious parts
- Include expected output

## 🎯 Documentation Touchpoint Map

For each type of change, update:

### New Feature
- [ ] README.md (features + example)
- [ ] docs/getting-started/concepts.md
- [ ] docs/guide/[feature].md (create new)
- [ ] docs/examples/[feature].md (create new)
- [ ] docs/api/[module].md
- [ ] Related guide files
- [ ] mkdocs.yml (navigation)

### API Change
- [ ] All docstrings
- [ ] docs/api/[module].md
- [ ] Related guides that use the API
- [ ] Examples that use the API
- [ ] Migration guide if breaking

### Behavior Change
- [ ] Relevant guide sections
- [ ] Examples that demonstrate behavior
- [ ] Docstrings with updated examples
- [ ] Troubleshooting/gotchas

### Bug Fix
- [ ] Add to troubleshooting if user-facing
- [ ] Update examples if bug was in example
- [ ] Add test to prevent regression

## 🔄 Continuous Improvement

- [ ] After user feedback, update FAQs
- [ ] Track common questions → add to docs
- [ ] Regularly review and refine examples
- [ ] Keep dependencies in examples up to date

---

**Remember: Documentation is not an afterthought—it's integral to the feature.**
