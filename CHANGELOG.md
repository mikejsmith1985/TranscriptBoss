# Changelog — TranscriptBoss

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Meeting transcriber: private in-browser transcription of system audio ("Others") and microphone (you) with Whisper, running on WebGPU or CPU; nothing is uploaded or saved
- Copy-for-Copilot prompt (summary, decisions, action-item table, risks) and .txt download
- Accurate / Fast model choice, remembered between visits
- Browser check page (`index.html`) that verifies system-audio capture, WebGPU, and model-host reachability before the full app is built
- Forge Workflow initialized with Forge Terminal Workflow Architect

### Changed
- Browser check moved to `/check/`

### Fixed

### Removed
