# Code Documentation Guide

This document outlines the documentation standards used in the ChannelFinWatcher project.

## Documentation Philosophy

We follow a **"code should be self-documenting"** approach with strategic documentation where it adds the most value:

1. **Document the "why", not the "what"** - Explain business logic, design decisions, and complex algorithms
2. **Focus on interfaces** - Public APIs, component props, function signatures
3. **Explain non-obvious behavior** - Edge cases, error handling, performance considerations
4. **Document architectural decisions** - Why we chose certain patterns or technologies

## Documentation Standards by File Type

### Python Backend (`/backend/app/`)

**Docstring Format**: Google-style docstrings for consistency with FastAPI auto-generated docs

```python
def extract_channel_info(self, url: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    Extract channel information from a YouTube URL.
    
    Args:
        url: YouTube channel URL to process
        
    Returns:
        Tuple of (success, channel_info_dict, error_message)
        
    Raises:
        DownloadError: When YouTube channel is inaccessible
        
    Example:
        success, info, error = service.extract_channel_info("https://youtube.com/@MrsRachel")
        if success:
            print(f"Channel: {info['name']} (ID: {info['channel_id']})")
    """
```

**What to Document**:
- ✅ Complex business logic (duplicate detection, URL normalization)
- ✅ Public API endpoints (FastAPI automatically uses docstrings)
- ✅ Service classes and their key methods
- ✅ Database models with design decisions
- ❌ Simple getters/setters or obvious utility functions

### TypeScript Frontend (`/frontend/src/`)

**Comment Format**: JSDoc for functions, interfaces, and complex components

```typescript
/**
 * Main component for adding and managing YouTube channels for monitoring.
 * 
 * This component implements Story 1: Add Channel via Web UI
 * - Provides form for entering YouTube channel URLs
 * - Validates input and calls backend API for channel creation
 * - Displays existing channels in card format
 * 
 * @returns JSX component for channel management
 */
export function YouTubeDownloader() {
```

**What to Document**:
- ✅ Component purpose and key features
- ✅ Complex state management logic
- ✅ API integration points
- ✅ Non-obvious business rules
- ❌ Simple UI components or standard React patterns

### Inline Comments

**Use for**:
- Complex algorithms or business logic
- Non-obvious code that might confuse future developers
- Workarounds or temporary solutions
- Performance-critical sections

```python
# Check for duplicate channels using YouTube's unique channel_id
# This prevents adding the same channel multiple times even with different URL formats
# (e.g., /@handle vs /channel/UC... URLs for the same channel)
existing = db.query(Channel).filter(Channel.channel_id == channel_info['channel_id']).first()
```

**Avoid for**:
- Explaining what the code does (code should be self-explanatory)
- Repeating variable names or obvious operations
- Commenting every line

## When Documentation is Most Valuable

### 1. **API Boundaries**
- Backend API endpoints (used by frontend)
- Service interfaces (used by other services)
- Component props and interfaces

### 2. **Business Logic**
- Channel deduplication strategy
- URL normalization rules
- Error handling workflows

### 3. **Complex Algorithms**
- YouTube URL validation regex patterns
- Database query optimization
- State management in React components

### 4. **Design Decisions**
- Why we check channel_id instead of URL for duplicates
- Why we normalize URLs on the backend vs frontend
- Database schema choices and constraints

## Documentation Maintenance

### When to Update Documentation
- ✅ When changing public APIs or interfaces
- ✅ When modifying complex business logic
- ✅ When fixing bugs that required deep investigation
- ✅ When adding new features with non-obvious behavior

### Documentation Review Checklist
- [ ] Does this explain WHY rather than WHAT?
- [ ] Would a new developer understand the business context?
- [ ] Are examples provided for complex functions?
- [ ] Is the documentation accurate and up-to-date?
- [ ] Does it explain error conditions and edge cases?

## Tools and Automation

### FastAPI Auto-Documentation
- Docstrings automatically appear in `/docs` Swagger UI
- Type hints are automatically documented
- Request/response schemas are auto-generated

### TypeScript IntelliSense
- JSDoc comments provide IDE tooltips and autocomplete
- Interface documentation appears in editor
- Type definitions serve as living documentation

## Example: Well-Documented Function

```python
def normalize_channel_url(self, url: str) -> str:
    """
    Normalize a YouTube channel URL to a standard format.
    
    This prevents duplicate channels when users enter different URL formats
    for the same channel (e.g., youtube.com vs www.youtube.com).
    
    Args:
        url: Input URL (may be missing protocol or have mobile domain)
        
    Returns:
        str: Normalized URL with https:// and www.youtube.com
        
    Example:
        normalize_channel_url("youtube.com/@channel") -> "https://www.youtube.com/@channel"
        normalize_channel_url("m.youtube.com/@channel") -> "https://www.youtube.com/@channel"
    """
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    # Ensure we use www.youtube.com for consistency (avoid double www)
    url = url.replace('://youtube.com', '://www.youtube.com')
    url = url.replace('://m.youtube.com', '://www.youtube.com')
    # Clean up any double-www that might occur
    url = url.replace('://www.www.youtube.com', '://www.youtube.com')
    
    return url
```

This example shows:
- Clear purpose and business context
- Parameter and return value documentation
- Concrete examples
- Inline comments for non-obvious logic
- Explanation of edge case handling (double-www bug fix)
