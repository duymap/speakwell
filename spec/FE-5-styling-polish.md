# FE-5: Styling & Polish

**Depends on:** FE-3 (ChatInterface), FE-4 (AudioIndicator)
**Team:** Frontend

---

## Objective

Polish the app's visual design, add responsive layout, improve error handling UX, and add connection recovery. This is the final frontend task before integration testing.

---

## Requirements

### 1. Overall Layout

The app should be a single full-height page with three sections:

```
┌─────────────────────────────────┐
│  Header: "SpeakWell" branding   │  ~60px fixed
├─────────────────────────────────┤
│                                 │
│  Transcript area (scrollable)   │  flex: 1
│                                 │
│  - User messages (right-aligned)│
│  - Bot messages (left-aligned)  │
│                                 │
├─────────────────────────────────┤
│  Audio indicator                │
│  [Start/End Conversation btn]   │  ~120px fixed
└─────────────────────────────────┘
```

```css
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 640px;
  margin: 0 auto;
}

.app-header {
  padding: 1rem;
  text-align: center;
  border-bottom: 1px solid #eee;
}

.chat-container {
  flex: 1;
  overflow: hidden; /* ChatInterface handles its own scrolling */
}

.app-footer {
  border-top: 1px solid #eee;
  padding: 0.75rem;
}
```

### 2. Responsive Design

| Breakpoint | Behavior |
|-----------|----------|
| Mobile (< 480px) | Full width, smaller fonts, compact padding |
| Tablet (480-768px) | Max-width 640px centered |
| Desktop (> 768px) | Max-width 640px centered, optional side margins |

```css
@media (max-width: 480px) {
  .app {
    max-width: 100%;
  }

  .message {
    margin-left: 0.5rem;
    margin-right: 0.5rem;
  }

  .connect-btn {
    width: 100%;
  }
}
```

### 3. Typography

- **Header:** 1.5rem, font-weight 700
- **Messages:** 1rem, line-height 1.6
- **Labels/meta:** 0.85rem, color #666
- **Font stack:** System fonts (already set in FE-1's CSS reset)

### 4. Color Palette

Keep it simple and accessible:

```css
:root {
  --color-primary: #1976d2;
  --color-primary-dark: #1565c0;
  --color-danger: #d32f2f;
  --color-danger-dark: #c62828;
  --color-user-msg: #e3f2fd;
  --color-bot-msg: #f5f5f5;
  --color-error: #ffebee;
  --color-error-text: #c62828;
  --color-text: #212121;
  --color-text-secondary: #666;
  --color-border: #e0e0e0;
  --color-bg: #ffffff;
}
```

### 5. Connection Error States

Improve the error UX from FE-3:

**Mic permission denied:**
```
┌──────────────────────────────────┐
│  🎤  Microphone Access Required  │
│                                  │
│  SpeakWell needs microphone      │
│  access to have a conversation.  │
│                                  │
│  [How to enable]  [Try Again]    │
└──────────────────────────────────┘
```

**Server unreachable:**
```
┌──────────────────────────────────┐
│  Connection Failed               │
│                                  │
│  Could not connect to the        │
│  server. Please try again.       │
│                                  │
│  [Retry]                         │
└──────────────────────────────────┘
```

**Disconnected unexpectedly:**
```
┌──────────────────────────────────┐
│  Connection Lost                 │
│                                  │
│  The conversation was            │
│  interrupted. Your transcript    │
│  is preserved above.             │
│                                  │
│  [Reconnect]  [Start New]        │
└──────────────────────────────────┘
```

### 6. Connection Recovery

Handle unexpected disconnections:

```tsx
useEffect(() => {
  // Watch for unexpected disconnection
  if (previousState === "connected" && client.state === "disconnected") {
    setConnectionLost(true);
  }
}, [client.state]);

// Reconnect handler
const handleReconnect = async () => {
  setConnectionLost(false);
  await handleConnect();
};
```

### 7. Loading State

While connecting, show a skeleton/loading state in the transcript area:

```tsx
{client.state === "connecting" && (
  <div className="connecting-state">
    <div className="spinner" />
    <p>Setting up your conversation...</p>
  </div>
)}
```

### 8. Message Timestamps (Optional)

Add timestamps to messages for reference:

```tsx
<div className="message">
  <div className="message-header">
    <span className="message-role">Tutor</span>
    <span className="message-time">2:34 PM</span>
  </div>
  <div className="message-text">...</div>
</div>
```

### 9. Smooth Message Appearance

New messages should fade in:

```css
.message {
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
```

### 10. Dark Mode (Optional, stretch goal)

```css
@media (prefers-color-scheme: dark) {
  :root {
    --color-bg: #121212;
    --color-text: #e0e0e0;
    --color-user-msg: #1a237e;
    --color-bot-msg: #2c2c2c;
    --color-border: #333;
  }
}
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/index.css` | CSS variables, dark mode, responsive breakpoints |
| `src/App.tsx` | Final layout structure |
| `src/App.css` | App-level layout styles |
| `src/components/ChatInterface.tsx` | Error states, loading, reconnection |
| `src/components/ChatInterface.css` | Message animations, improved styling |
| `src/components/AudioIndicator.css` | Responsive sizing |

---

## Testing

### Visual Checklist

- [ ] App looks good on mobile (375px wide)
- [ ] App looks good on tablet (768px wide)
- [ ] App looks good on desktop (1440px wide)
- [ ] Messages are readable with good contrast
- [ ] Button states are visually distinct
- [ ] Error messages are clear and actionable
- [ ] Animations are smooth
- [ ] Transcript scrolls correctly with many messages

### Error State Testing

1. Start app with backend stopped → "Connection Failed" error
2. Deny mic permission → "Microphone Access Required" error
3. Connect successfully, then kill the backend → "Connection Lost" state
4. Click "Reconnect" after restarting backend → conversation resumes

---

## Acceptance Criteria

- [ ] App has a polished, professional appearance
- [ ] Responsive on mobile, tablet, and desktop
- [ ] CSS variables for consistent theming
- [ ] Error states have clear messaging and recovery actions
- [ ] Unexpected disconnection shows reconnect option
- [ ] Loading state while connecting
- [ ] Messages animate in smoothly
- [ ] No horizontal scrolling on any viewport
- [ ] All interactive elements have hover/active/disabled states
- [ ] Accessibility: sufficient color contrast, focus outlines, semantic HTML
