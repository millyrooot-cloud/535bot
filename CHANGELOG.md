# Kelley Compass AI - Changelog

## [2.0] - April 6, 2026

### Added
- **Conversation Memory**: Bot remembers full chat history across turns
- **Optional Form Fields**: All profile fields are optional - get advice with minimal info
- **Professional UI/UX**: Complete redesign with corporate university aesthetic
- **Smooth Animations**: Refined transitions using cubic-bezier easing
- **Loading States**: Visual feedback for all async operations
- **Typing Indicator**: Animated dots while waiting for bot response
- **Better Error Handling**: Graceful fallbacks with helpful messages
- **Responsive Design**: Mobile-friendly layout with collapsible sidebar
- **Session Management**: Server-side conversation and transcript storage

### Improved
- Message animations: Smooth cubic-bezier easing (0.4s) instead of linear
- Button transitions: 0.3s smooth transitions on all interactions
- Form field focus: Enhanced visual feedback with box-shadow
- Typing dots: Larger, more visible animation
- Message spacing: Increased gap for better breathing room (1.25rem)
- Chat scrolling: Uses requestAnimationFrame for 60fps smoothness
- System prompt: Includes student context for better follow-up responses
- Error messages: Better styling and visibility

### Changed
- UI: Moved from cluttered multi-view to clean sidebar + chat layout
- Backend: Single unified `/api/chat` endpoint instead of multiple routes
- Frontend: Plain HTML/CSS/JS instead of React for simplicity
- Form submission: All fields optional, sensible defaults for missing data
- Loading flow: Staggered message timing (150ms → 500ms → 800ms) for natural feel

### Removed
- Old React components
- Multiple conflicting API endpoints
- Repeated/confusing views
- Complex form validation

## [1.0] - April 5, 2026

### Initial Release
- Flask backend with Groq AI integration
- Basic HTML/CSS/JS frontend
- Transcript parsing and course extraction
- I-Core prerequisite checking
- Major requirement mapping
- Simple chat interface
