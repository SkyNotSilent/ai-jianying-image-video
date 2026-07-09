# GitHub Settings

## Repository Identity

Recommended public repository name:

```text
ai-jianying-image-video
```

Product name:

```text
InsightCut
```

Recommended description:

```text
AI 图片视频生成工作台：文稿/主题转视频，分镜可编辑，生成效果远胜剪映一键成片，支持 MP4 与剪映/CapCut 草稿导出。
```

Recommended topics:

```text
jianying
capcut
ai-video
ai-image-video
image-to-video
explainer-video
storyboard
tts
fastapi
vue3
local-first
```

Public disclaimer:

```text
This project is not affiliated with Jianying, CapCut, or ByteDance.
```

## Branch Protection

Protect `master` with:

- Require a pull request before merging.
- Require status checks to pass before merging.
- Required checks:
  - `Backend compile`
  - `Frontend build`
  - `Repository hygiene`
- Block force pushes.
- Block branch deletion.
- Keep administrator bypass enabled only for emergency recovery.

## PR Policy

- Default to draft PRs until validation is complete.
- Use PR template fields as the merge checklist.
- UI changes need screenshots.
- Generated-output changes need screenshots or compressed video.
- Pipeline changes must preserve assets for failed and partially failed tasks.

## Release Policy

- Tag stable local-first batches as `v0.1.x`.
- Release notes should include:
  - Product changes.
  - Engineering changes.
  - Validation commands.
  - Screenshots or showcase videos.
  - Known limitations.
