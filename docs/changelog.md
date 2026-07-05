# Changelog

This page mirrors the [CHANGELOG.md](https://github.com/sina-al/pymediate/blob/main/CHANGELOG.md) at the repository root, which is generated from Conventional Commits with [git-cliff](https://git-cliff.org/) on each release. It's regenerated automatically by `uv run poe changelog` — don't hand-edit it.

## [Unreleased]

### Documentation

- Apply Microsoft writing style to top-level docs, fix stale DI terminology ([3a47ee7](https://github.com/sina-al/pymediate/commit/3a47ee7aa81b7160b9b2cc53e128875d623ec255))
- Remove Zero convention and Dataclass friendly from feature lists ([7798b81](https://github.com/sina-al/pymediate/commit/7798b815c46a5ae186351830558c367f380cd1e0))

## [0.1.1] - 2026-07-05

### Documentation

- Rewrite entire docs/ site in Microsoft style, fix broken examples ([bec767f](https://github.com/sina-al/pymediate/commit/bec767fa98480faca25791f00a499a32f591faca))

### Fixes

- Correct broken HandlerNotFoundError message and docstring inaccuracies ([6688e7c](https://github.com/sina-al/pymediate/commit/6688e7caa2dc486631cc16ceb79fdfcc6badcf70))

### Miscellaneous

- Scope Documentation workflow to docs-relevant path changes ([011b46f](https://github.com/sina-al/pymediate/commit/011b46f63c4742567ca38c8dd99f2a07c77e5584))
- *(release)* V0.1.1 ([1c2a8ed](https://github.com/sina-al/pymediate/commit/1c2a8ede0c20b74c009c326e829cdddc190df645))

## [0.1.0] - 2026-07-05

### Build system

- Migrate to uv's native build backend (uv_build) ([4d6944c](https://github.com/sina-al/pymediate/commit/4d6944c17f934907465c33fb64137d29ba195a2e))

### Documentation

- Update docs ([a02d1f4](https://github.com/sina-al/pymediate/commit/a02d1f485675b4a95cf38486bb897648b8ec283c))
- Add docs ([948677f](https://github.com/sina-al/pymediate/commit/948677f0c0bf2bf631e6d28d4ec5679d952f1ad5))

- Update docs ([b74cb23](https://github.com/sina-al/pymediate/commit/b74cb23e7f0a375697d7ebdc8766ad9574653d4c))
- Fix logo render ([1f4a440](https://github.com/sina-al/pymediate/commit/1f4a440605706f73a38437eeba2dce4e4e0fe620))

- Update readme styling ([97a2813](https://github.com/sina-al/pymediate/commit/97a28133c3b79354ccab29dc7b7c68a008a572af))
- Update tagline ([af7ffae](https://github.com/sina-al/pymediate/commit/af7ffae1d3f5a5d6fabf104697c3928a909dc923))

- Strip api reference ([279bbeb](https://github.com/sina-al/pymediate/commit/279bbeb467dd39863e04104ff86d655d6b3622c8))
- Fix badges ([2567506](https://github.com/sina-al/pymediate/commit/2567506715b9ebacaa1c33cca725aaf39e7637f6))

- Remove codecov badge ([346eb18](https://github.com/sina-al/pymediate/commit/346eb1829258decaca0bad9a7442b45115fc7f8f))
- Trim docs ([df20472](https://github.com/sina-al/pymediate/commit/df20472f31111872c7e72a3e958468acb66b3513))

- Update docs ([8163302](https://github.com/sina-al/pymediate/commit/81633020e1f8aec94eded670fff6cb3490d593eb))
- Add /release skill with the full release checklist ([1d0b860](https://github.com/sina-al/pymediate/commit/1d0b8608a9d22202a3dc043e346e9dcf8b8c0cb6))

### Features

- Registry api ([c168b01](https://github.com/sina-al/pymediate/commit/c168b018cab8cb90f6ac2d04ead4c0f222c8807e))
- Extend aio support ([2968d6e](https://github.com/sina-al/pymediate/commit/2968d6e759f0783cc33edec69349f857bb584a33))

- Add service provider protocol ([1752dc0](https://github.com/sina-al/pymediate/commit/1752dc0b3642b79264b7fa0b70e7cbe1c7608613))
- Pipeline behaviours ([48a1de7](https://github.com/sina-al/pymediate/commit/48a1de74ae80784cb7060c5dd2af756d648fd861))

- Integrate pipeline behaviours in mediator ([c8c3c26](https://github.com/sina-al/pymediate/commit/c8c3c268eaee4b40dbf2ffb7bd3d7f671d056249))
- Pin uv version and add a scripted, parameterized way to bump it ([2ab794a](https://github.com/sina-al/pymediate/commit/2ab794a76f87a27d5348f5ed4e093d62a654fe2c))

- Implement packaging audit findings — metadata, publish pipeline, community files ([f29e858](https://github.com/sina-al/pymediate/commit/f29e8580392657020a2c9971154d507f9dd1a993))
- Modernize release pipeline per PyPA + uv publishing guidance ([783cec7](https://github.com/sina-al/pymediate/commit/783cec79c66f44bd7c1780774717b1777bf043fd))

### Fixes

- Fix lint issue ([7a62fc7](https://github.com/sina-al/pymediate/commit/7a62fc7c50a257698c17e9597c6f62fd3aa47d06))
- Workflows ([52ac696](https://github.com/sina-al/pymediate/commit/52ac696aaf397a44c9dd3be8d0b0177243bb4a4e))

- Simplify workflows ([8439052](https://github.com/sina-al/pymediate/commit/84390521a91e11db53894d321c9f3adf78d08ef2))
- Enable-cache = false ([fe0684d](https://github.com/sina-al/pymediate/commit/fe0684da8fe36875a030b6ff3cc5d1811b106401))

- Uv sync in workflows ([c1c312c](https://github.com/sina-al/pymediate/commit/c1c312c7aa0e94a83aae7d287a4f4824f38da611))
- Hack typing ([0e31b6d](https://github.com/sina-al/pymediate/commit/0e31b6de6d76236b702e7deba965df7b023c5849))

- Mypy typing ([9127c83](https://github.com/sina-al/pymediate/commit/9127c8301db064cbdab4bde835c0ed93fd377943))
- Testes ([7919e3a](https://github.com/sina-al/pymediate/commit/7919e3a6aacf7ec3ffb516e6debca504f6eb1e99))

- Pin dependency versions via committed uv.lock, fix mypy test flakiness ([8eee494](https://github.com/sina-al/pymediate/commit/8eee4945b49f62b1e4abbc606faa309495366ef8))
- Ide settings ([fb40073](https://github.com/sina-al/pymediate/commit/fb400736321bad60bcbabb8fea21b7868bd4c868))

- Deploy docs via GitHub Actions Pages flow instead of gh-deploy ([1387265](https://github.com/sina-al/pymediate/commit/138726560accdbdf0425bb6d49fa3a84b029c5a4))
- Pin orgoro/coverage to exact release, skip it on non-PR events ([4eed737](https://github.com/sina-al/pymediate/commit/4eed737fca628d45dda37576c254c2622a435e6d))

- Correct stale imports and Python version matrix in release.yml/docs ([eba8436](https://github.com/sina-al/pymediate/commit/eba8436416d9d2ddcec347065ed515a067d0851f))
- Close coverage gap to 95% floor, remove dead error classes ([d5d5e06](https://github.com/sina-al/pymediate/commit/d5d5e06e08de7d2a67abe3e6fcddfc0edb8c2af3))

- Expand wheel glob before appending [di] extra in release.yml ([e872e39](https://github.com/sina-al/pymediate/commit/e872e397c32069a160fc65d02e4e0364d4bb6e8a))
- Checkout repo in publish-testpypi/publish-pypi jobs ([575f960](https://github.com/sina-al/pymediate/commit/575f960cbf8d445b226e27cfff8eef802ef32871))

- Force --trusted-publishing always on both publish steps ([2d36650](https://github.com/sina-al/pymediate/commit/2d366501f5609f1186fb1fe64f2044e85a7c2021))

### Miscellaneous

- Fix logo ([e536c53](https://github.com/sina-al/pymediate/commit/e536c5327422fe65861e6adf1d0725cd651b9c36))
- Disable cache ([9d3af9a](https://github.com/sina-al/pymediate/commit/9d3af9ac781ec7750af6a297dce6037baaabb653))

- Simplify workflow ([73910c4](https://github.com/sina-al/pymediate/commit/73910c4eb4fcc0b31a12c0b8697d3fff8540e8be))
- Clean workflows ([d5c0b60](https://github.com/sina-al/pymediate/commit/d5c0b6056d464606a8e071cc0f98866bdf435ac7))

- Fix badges ([a68dba8](https://github.com/sina-al/pymediate/commit/a68dba8ce4bf79575b68e624635a056898fa06e3))
- Restructure packages ([7991d9c](https://github.com/sina-al/pymediate/commit/7991d9c588cbbf840bfe9ac127a83f0d2bd52e91))

- Rename modules ([4eda44e](https://github.com/sina-al/pymediate/commit/4eda44e9c698508c50902d680854427de2b8056a))
- Refactor resolver protocol ([f92305a](https://github.com/sina-al/pymediate/commit/f92305a00e46f7ff51e7c62256e1bea6a0fac1fa))

- Refactor to use service provider protocol ([72b3ac6](https://github.com/sina-al/pymediate/commit/72b3ac667dd816b77b2b93f3aebf20fd6ef04362))
- Remove legacy code ([d69d6c5](https://github.com/sina-al/pymediate/commit/d69d6c511342a11ce0948c63644163c3b5805fb7))

- Renaming ([5f44389](https://github.com/sina-al/pymediate/commit/5f4438989a62736a6b98583b681be6b68f68d7f2))
- Improve registry ([47250ab](https://github.com/sina-al/pymediate/commit/47250ab679c1fac4e8e0f3466aeaa58da4e25289))

- Refactor pipeline behaviour class ([ace50bb](https://github.com/sina-al/pymediate/commit/ace50bb7f2b6e7e1fcd229d7c607cd3b573e900d))
- Simplfy pipeline behavior ([39bffd6](https://github.com/sina-al/pymediate/commit/39bffd6b4d86fa22523bc088e21e7a38a1f2e22d))

- Rename files ([7b3aa1c](https://github.com/sina-al/pymediate/commit/7b3aa1c032eb94aefedf4f93d98357eecea796c3))
- Bump GitHub Actions to versions running on Node 24 ([63f159e](https://github.com/sina-al/pymediate/commit/63f159eafee729a23c926d8a1bea0f099d07f7d4))

- Add Dependabot config for github-actions ecosystem ([760484b](https://github.com/sina-al/pymediate/commit/760484bb62abcaaf01f6b99a23e38474cc91982f))
- Rename Pages deployment environment github-pages -> documentation ([3759f29](https://github.com/sina-al/pymediate/commit/3759f29265c53d47a7e3b5c020670ca944188853))

- *(release)* V0.1.0 ([5cb6394](https://github.com/sina-al/pymediate/commit/5cb63947b22e4d67959e87f24419876e2cb7153a))

### Refactoring

- Favor poe tasks over freely-defined uv/tool invocations in CI ([52377af](https://github.com/sina-al/pymediate/commit/52377aff9a415d2b9ae9282be93087b5caca6a6a))

### Testing

- Add mypytest ([70b840c](https://github.com/sina-al/pymediate/commit/70b840cff06bdb1762baf33f6a59adc7bc080f4a))
- Improve test structure ([22a4bac](https://github.com/sina-al/pymediate/commit/22a4bac4adeb3dae90c4ed49a4d31f568d8bf20c))

