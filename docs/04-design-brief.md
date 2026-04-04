# SOFIE — UI/UX Design Brief
**For Claude Code execution via STITCH + UIUX Pro Max**
**Version:** 1.0
**Last Updated:** 2026-04-04

---

## 1. Design Tools

**Primary:** STITCH (Google Design MCP) — use for layout generation, component design, and visual mockups.
**Secondary:** UIUX Pro Max skill (nextlevelbuilder.io) — use for design system selection, colour palettes, typography pairings, and UX guidelines.
**Implementation:** React + Tailwind CSS

**IMPORTANT:** Claude Code must call STITCH MCP and UIUX Pro Max skill for ALL visual design decisions. Do not freestyle CSS or layout. Generate via these tools first, then implement.

---

## 2. Product Context

SOFIE is a chatbot that acts as a creative account manager for social media agencies. The primary user is a **brand client** (marketing manager at a consumer brand) who chats with "Sofie" to request social media visuals.

The secondary user is a **Qurious Media operator** who reviews and approves generated content before it reaches the client.

---

## 3. Design Principles

1. **Feels like messaging, not software.** The chat should feel as natural as WhatsApp or iMessage. Not a ticketing system.
2. **Images are first-class.** Generated images should display large, sharp, and prominent in chat. Not as tiny thumbnails.
3. **Trust through transparency.** Show Sofie's thinking process subtly ("Pulling up your brand guidelines..." "Generating your visual..."). Users should never wonder what's happening.
4. **Agency-grade aesthetics.** This is a creative tool for creative people. It must look polished enough that a design agency wouldn't be embarrassed to show it to clients.

---

## 4. Screens

### Screen 1: Chat Interface (Primary)
**Users:** Brand client, Agency operator
**Layout:**
- Full-height chat window (mobile-friendly, desktop-optimised)
- Left sidebar (optional, desktop only): brand selector, conversation history
- Main area: message stream with Sofie's avatar, text bubbles, inline image previews
- Bottom: text input bar with send button, attachment button (future)
- Top bar: brand name, Sofie status indicator (online/generating)

**Key interactions:**
- User types message → Sofie responds in real-time (streaming text via WebSocket)
- When generating an image: show progress indicator ("Creating your visual..." with subtle animation)
- Generated image appears as a large preview card in chat (not a raw image dump)
- Image card has: preview, "Download" button, "Request changes" button
- Sofie's messages should have a distinct visual treatment from user messages

**Image preview card spec:**
- Max width: 480px (desktop), full width (mobile)
- Rounded corners (12px)
- Shadow for depth
- Below image: brief caption from Sofie ("Here's your Hari Raya post — warm golds with your family imagery")
- Action buttons: Download (primary), Request Changes (secondary)

**Sofie's avatar:**
- Small circular avatar next to Sofie's messages
- Design a simple, friendly, gender-neutral avatar mark (not a photo, not a generic bot icon)
- Colour: should complement the overall UI palette

### Screen 2: Approval Dashboard
**Users:** Qurious Media operators only
**Layout:**
- Card grid or list view of pending approvals
- Each card: brand name, brief summary (2 lines), generated image thumbnail, compliance score badge, timestamp
- Click card → expands to full detail: large image, full brief, compliance notes, operator action buttons
- Actions: Approve (green), Reject with notes (red, opens text field)
- Filter by: brand, status, date
- Simple top nav with "Pending" count badge

**Style:** Cleaner, more utilitarian than the chat UI. Think: internal tool, not customer-facing.

### Screen 3: Brand Setup (Future, Minimal for POC)
**Users:** Admin
**Layout:**
- Simple form: brand name, upload brand.md, upload logo, upload font, upload reference images
- List of existing brands with edit/delete
- Not a priority for design — functional is fine for POC

---

## 5. Visual Direction

**Overall feel:** Modern, warm, confident. Not cold/corporate. Not playful/childish.

**Colour guidance for UIUX Pro Max:**
- Request a palette that feels: professional yet approachable, suitable for a creative industry tool
- Primary: a warm neutral or soft navy (not stark black or bright blue)
- Accent: a warm highlight colour (coral, amber, or warm gold)
- Backgrounds: off-white or very light warm grey
- Error/warning: standard red/amber but softened

**Typography guidance for UIUX Pro Max:**
- Request a font pairing suitable for: a chat interface with headings
- Chat text: highly legible sans-serif at 14-16px
- Headings: slightly more personality, still clean
- Monospace: for any code/JSON display (debugging only)

**Spacing and density:**
- Chat messages: generous vertical spacing (not cramped)
- Approval dashboard: tighter grid, efficient use of space
- Overall: airy, not dense

---

## 6. Responsive Behaviour

| Breakpoint | Layout |
|---|---|
| Mobile (<768px) | Full-screen chat, no sidebar. Approval dashboard as stacked cards. |
| Tablet (768-1024px) | Chat with collapsible sidebar. Approval as 2-column grid. |
| Desktop (>1024px) | Chat with persistent sidebar. Approval as 3-column grid. |

---

## 7. Loading and Status States

| State | Visual Treatment |
|---|---|
| Sofie thinking | Typing indicator (3 animated dots) in Sofie's bubble |
| Image generating | Progress card in chat: "Creating your visual..." with subtle pulse animation. Optional: show step labels (Composing layout... Applying brand elements... Checking compliance...) |
| Image ready | Image card slides in with a gentle entrance animation |
| Approval pending | Badge with count on approval nav item |
| Error | Sofie says "I ran into a snag generating that. Let me try a different approach." — never show stack traces to the user |

---

## 8. Accessibility (Minimum)

- Colour contrast: WCAG AA minimum
- All images: alt text (generated by LLM from the brief)
- Keyboard navigation: tab through chat input, send button, image actions
- Screen reader: proper ARIA labels on interactive elements

---

## 9. What Claude Code Should Do

1. **Before writing any frontend code:** Call UIUX Pro Max to generate a colour palette and font pairing based on §5 above.
2. **Before building any screen:** Call STITCH to generate the layout/mockup based on the screen specs in §4.
3. **Implement** the STITCH output using React + Tailwind.
4. **Do not** invent colours, fonts, or layouts without consulting these tools first.
5. **Do not** use default Tailwind greys or blues. Use the generated palette.

---

## 10. Cross-References

- [[01-project-plan]] — Project Plan
- [[02-prd]] — Product Requirements Document
- [[03-tdd]] — Technical Design Document
- [[05-claude-md]] — Claude Code Instruction File
