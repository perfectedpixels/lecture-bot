# Contextual Learning Cards - Implementation Tasks

## Phase 1: Data Preparation

### Task 1.1: Portfolio Image Tagging ✅ COMPLETE
- [x] 1.1.1 Run automated tagging script on all 208 images
- [x] 1.1.2 Review Claude's suggested tags for accuracy
- [x] 1.1.3 Manually refine tags using review tool
- [x] 1.1.4 Validate metadata JSON structure
- [ ] 1.1.5 Upload `portfolio_image_metadata.json` to S3

**Estimated Time:** 2-3 hours
**Dependencies:** None
**Deliverable:** `data/portfolio_image_metadata.json` ✅

### Task 1.2: Create Teaching Concepts Taxonomy ✅ COMPLETE
- [x] 1.2.1 Define 20 high-level teaching concepts
- [x] 1.2.2 Write definitions for each concept
- [x] 1.2.3 List key principles for each concept
- [x] 1.2.4 Map concepts to affinity clusters
- [x] 1.2.5 Add keywords and example deliverables
- [x] 1.2.6 Create `teaching_concepts.json` file
- [ ] 1.2.7 Upload to S3

**Estimated Time:** 3-4 hours
**Dependencies:** Affinity map must exist
**Deliverable:** `data/teaching_concepts.json` ✅

### Task 1.3: Lecture-Portfolio Cross-Reference ✅ COMPLETE
- [x] 1.3.1 Extract all portfolio project mentions from lecture transcripts
- [x] 1.3.2 Use Claude to analyze context of each mention
- [x] 1.3.3 Link mentions to specific lecture segments
- [x] 1.3.4 Add `lecture_mentions` to portfolio metadata
- [x] 1.3.5 Validate cross-references
- [ ] 1.3.6 Upload updated metadata to S3

**Estimated Time:** 2-3 hours
**Dependencies:** Task 1.1 complete, lecture transcripts available
**Deliverable:** Updated `portfolio_image_metadata.json` with lecture mentions ✅

**Phase 1 Status:** Data preparation complete! Found 44 portfolio mentions across 5 projects (Amazon, AWS, Microsoft, Trulia, All-Recipes). Ready for Phase 2.

## Phase 2: Backend Implementation

### Task 2.1: Create LearningCardGenerator Class ✅ COMPLETE
- [x] 2.1.1 Create `src/learning_card_generator.py`
- [x] 2.1.2 Implement `__init__()` with data loading
- [x] 2.1.3 Implement `generate_cards()` main method
- [x] 2.1.4 Add error handling and logging
- [x] 2.1.5 Write unit tests

**Estimated Time:** 3-4 hours
**Dependencies:** Task 1.2 complete
**Deliverable:** `src/learning_card_generator.py` ✅

### Task 2.2: Implement Related Concepts Analysis ✅ COMPLETE
- [x] 2.2.1 Implement `analyze_related_concepts()` method
- [x] 2.2.2 Add logic to find concepts in same cluster
- [x] 2.2.3 Add logic to find concepts in related clusters
- [x] 2.2.4 Filter out already-discussed concepts
- [x] 2.2.5 Rank by relevance (affinity scores)
- [x] 2.2.6 Return top 3-5 concepts with previews
- [x] 2.2.7 Write unit tests

**Estimated Time:** 2-3 hours
**Dependencies:** Task 2.1 complete, affinity map available
**Deliverable:** Working `analyze_related_concepts()` method ✅
**Note:** Requires affinity_map.json to be generated

### Task 2.3: Implement Teaching Concepts Identification ✅ COMPLETE
- [x] 2.3.1 Implement `identify_teaching_concepts()` method
- [x] 2.3.2 Add keyword matching logic
- [x] 2.3.3 Use Claude to analyze query/answer relevance
- [x] 2.3.4 Map to teaching concepts taxonomy
- [x] 2.3.5 Rank by relevance
- [x] 2.3.6 Return top 3-5 teaching concepts
- [x] 2.3.7 Write unit tests

**Estimated Time:** 2-3 hours
**Dependencies:** Task 2.1 complete, Task 1.2 complete
**Deliverable:** Working `identify_teaching_concepts()` method ✅

### Task 2.4: Implement Portfolio Examples Finder ✅ COMPLETE
- [x] 2.4.1 Implement `find_portfolio_examples()` method
- [x] 2.4.2 Add concept tag matching logic
- [x] 2.4.3 Add teaching concept matching logic
- [x] 2.4.4 Add lecture mention matching logic
- [x] 2.4.5 Rank by relevance (multiple factors)
- [x] 2.4.6 Return top 1-3 projects with images
- [x] 2.4.7 Write unit tests

**Estimated Time:** 2-3 hours
**Dependencies:** Task 2.1 complete, Task 1.1 and 1.3 complete
**Deliverable:** Working `find_portfolio_examples()` method ✅

### Task 2.5: Implement Inline Content Fetching ✅ COMPLETE
- [x] 2.5.1 Implement `get_inline_content()` method
- [x] 2.5.2 Query Knowledge Base for concept-specific segments
- [x] 2.5.3 Format content for display
- [x] 2.5.4 Add caching to avoid redundant queries
- [x] 2.5.5 Handle errors gracefully
- [x] 2.5.6 Write unit tests

**Estimated Time:** 2 hours
**Dependencies:** Task 2.1 complete, Bedrock KB access
**Deliverable:** Working `get_inline_content()` method ✅

### Task 2.6: Enhance PersonaBot Integration ✅ COMPLETE
- [x] 2.6.1 Add LearningCardGenerator to PersonaBot `__init__()`
- [x] 2.6.2 Modify `query()` to call `generate_cards()`
- [x] 2.6.3 Add `learning_cards` to response dict
- [x] 2.6.4 Handle case where card generation fails
- [x] 2.6.5 Add logging for card generation
- [x] 2.6.6 Update unit tests

**Estimated Time:** 1-2 hours
**Dependencies:** Tasks 2.1-2.5 complete
**Deliverable:** Enhanced `src/persona_bot_safe.py` ✅

**Phase 2 Status:** Backend implementation complete! All three card types are generating successfully. Ready for Phase 3 (UI Implementation).

## Phase 3: UI Implementation

### Task 3.1: Create Card Rendering Components ✅ COMPLETE
- [x] 3.1.1 Create `render_learning_cards()` function
- [x] 3.1.2 Create `render_related_concepts_card()` function
- [x] 3.1.3 Create `render_teaching_concepts_card()` function
- [x] 3.1.4 Create `render_portfolio_card()` function
- [x] 3.1.5 Add helper function for inline expansion
- [x] 3.1.6 Test each component individually

**Estimated Time:** 3-4 hours
**Dependencies:** None (can start in parallel with Phase 2)
**Deliverable:** Card rendering functions in `app/streamlit_app_redesign.py` ✅

### Task 3.2: Add CSS Styling for Cards ✅ COMPLETE
- [x] 3.2.1 Design card container styles
- [x] 3.2.2 Design concept item styles
- [x] 3.2.3 Design portfolio project styles
- [x] 3.2.4 Add hover effects and transitions
- [x] 3.2.5 Ensure mobile responsiveness
- [x] 3.2.6 Test on different screen sizes

**Estimated Time:** 2-3 hours
**Dependencies:** Task 3.1 complete
**Deliverable:** CSS styles in `app/streamlit_app_redesign.py` ✅

### Task 3.3: Implement Inline Expansion Logic ✅ COMPLETE
- [x] 3.3.1 Add session state for expanded concepts
- [x] 3.3.2 Implement expand/collapse toggle
- [x] 3.3.3 Add "Learn more" button functionality
- [x] 3.3.4 Fetch inline content on expansion
- [x] 3.3.5 Display loading state while fetching
- [x] 3.3.6 Handle expansion errors gracefully

**Estimated Time:** 2-3 hours
**Dependencies:** Task 3.1 complete, Task 2.5 complete
**Deliverable:** Working inline expansion in UI ✅

### Task 3.4: Implement "Ask Professor Levine" Action ✅ COMPLETE
- [x] 3.4.1 Add button to submit concept as new query
- [x] 3.4.2 Format query appropriately
- [x] 3.4.3 Update `pending_question` session state
- [x] 3.4.4 Trigger rerun to process query
- [x] 3.4.5 Test query submission flow

**Estimated Time:** 1 hour
**Dependencies:** Task 3.3 complete
**Deliverable:** Working "Ask Professor Levine" buttons ✅

### Task 3.5: Integrate Cards into Chat Display ✅ COMPLETE
- [x] 3.5.1 Modify chat history display loop
- [x] 3.5.2 Call `render_learning_cards()` after each bot response
- [x] 3.5.3 Only show cards for most recent message
- [x] 3.5.4 Handle case where no cards are generated
- [x] 3.5.5 Test with multiple messages in history

**Estimated Time:** 1-2 hours
**Dependencies:** Tasks 3.1-3.4 complete
**Deliverable:** Cards integrated into chat UI ✅

### Task 3.6: Remove Old "Dive Deeper" Buttons ✅ COMPLETE
- [x] 3.6.1 Remove follow-up prompt buttons code
- [x] 3.6.2 Clean up related session state
- [x] 3.6.3 Test that removal doesn't break anything
- [x] 3.6.4 Update UI to ensure no visual gaps

**Estimated Time:** 30 minutes
**Dependencies:** Task 3.5 complete
**Deliverable:** Cleaned up UI without old buttons ✅

**Phase 3 Status:** UI implementation complete! Learning cards are now displayed with inline expansion, "Ask Professor Levine" buttons, and portfolio examples. Old "Dive deeper" buttons removed. Ready for Phase 4 (Integration & Testing).

## Phase 4: Integration & Testing

### Task 4.1: End-to-End Integration Testing
- [ ] 4.1.1 Test complete flow: query → cards → expansion → new query
- [ ] 4.1.2 Test with various query types (concepts, projects, methods)
- [ ] 4.1.3 Test error cases (no cards, failed expansion, etc.)
- [ ] 4.1.4 Test session state management
- [ ] 4.1.5 Test with multiple users/sessions

**Estimated Time:** 2-3 hours
**Dependencies:** All Phase 2 and 3 tasks complete
**Deliverable:** Test report with issues identified

### Task 4.2: Performance Optimization
- [ ] 4.2.1 Measure card generation time
- [ ] 4.2.2 Measure inline expansion time
- [ ] 4.2.3 Add caching where beneficial
- [ ] 4.2.4 Optimize Knowledge Base queries
- [ ] 4.2.5 Lazy load images
- [ ] 4.2.6 Re-measure and verify improvements

**Estimated Time:** 2-3 hours
**Dependencies:** Task 4.1 complete
**Deliverable:** Performance metrics and optimizations

### Task 4.3: Mobile Responsiveness Testing
- [ ] 4.3.1 Test on mobile browsers (iOS Safari, Android Chrome)
- [ ] 4.3.2 Verify cards stack properly
- [ ] 4.3.3 Verify expansion works on touch
- [ ] 4.3.4 Verify images load and display correctly
- [ ] 4.3.5 Fix any mobile-specific issues

**Estimated Time:** 1-2 hours
**Dependencies:** Task 3.2 complete
**Deliverable:** Mobile-friendly card UI

### Task 4.4: Content Quality Review
- [ ] 4.4.1 Review suggested concepts for relevance
- [ ] 4.4.2 Review teaching concept mappings
- [ ] 4.4.3 Review portfolio example matches
- [ ] 4.4.4 Refine algorithms based on findings
- [ ] 4.4.5 Update data (taxonomy, metadata) as needed

**Estimated Time:** 2-3 hours
**Dependencies:** Task 4.1 complete
**Deliverable:** Quality assessment report and refinements

## Phase 5: Deployment

### Task 5.1: Deploy Data to S3
- [ ] 5.1.1 Upload `teaching_concepts.json` to S3
- [ ] 5.1.2 Upload `portfolio_image_metadata.json` to S3
- [ ] 5.1.3 Verify S3 paths are correct in code
- [ ] 5.1.4 Test data loading from S3

**Estimated Time:** 30 minutes
**Dependencies:** Tasks 1.1, 1.2, 1.3 complete
**Deliverable:** Data files in S3

### Task 5.2: Deploy Backend Code
- [ ] 5.2.1 Sync `src/learning_card_generator.py` to EC2
- [ ] 5.2.2 Sync updated `src/persona_bot_safe.py` to EC2
- [ ] 5.2.3 Install any new dependencies
- [ ] 5.2.4 Test backend on EC2

**Estimated Time:** 30 minutes
**Dependencies:** Phase 2 complete, Task 5.1 complete
**Deliverable:** Backend deployed to EC2

### Task 5.3: Deploy UI Code
- [ ] 5.3.1 Sync updated `app/streamlit_app_redesign.py` to EC2
- [ ] 5.3.2 Restart Streamlit service
- [ ] 5.3.3 Verify app loads without errors
- [ ] 5.3.4 Test basic functionality

**Estimated Time:** 30 minutes
**Dependencies:** Phase 3 complete, Task 5.2 complete
**Deliverable:** UI deployed to EC2

### Task 5.4: Production Testing
- [ ] 5.4.1 Test on production URL
- [ ] 5.4.2 Verify cards appear correctly
- [ ] 5.4.3 Verify inline expansion works
- [ ] 5.4.4 Verify images load from S3
- [ ] 5.4.5 Test with real student queries

**Estimated Time:** 1 hour
**Dependencies:** Tasks 5.1-5.3 complete
**Deliverable:** Production system verified working

### Task 5.5: Monitoring Setup
- [ ] 5.5.1 Add logging for card generation
- [ ] 5.5.2 Add logging for inline expansion
- [ ] 5.5.3 Set up CloudWatch dashboard (optional)
- [ ] 5.5.4 Document how to check logs
- [ ] 5.5.5 Set up alerts for errors (optional)

**Estimated Time:** 1-2 hours
**Dependencies:** Task 5.4 complete
**Deliverable:** Monitoring and logging in place

## Phase 6: Documentation & Handoff

### Task 6.1: Update Documentation
- [ ] 6.1.1 Update README with new features
- [ ] 6.1.2 Update ARCHITECTURE.md with card system
- [ ] 6.1.3 Create user guide for students
- [ ] 6.1.4 Create maintenance guide for instructors
- [ ] 6.1.5 Document data schemas

**Estimated Time:** 2-3 hours
**Dependencies:** Phase 5 complete
**Deliverable:** Updated documentation

### Task 6.2: Create Demo Video
- [ ] 6.2.1 Record demo of card features
- [ ] 6.2.2 Show inline expansion
- [ ] 6.2.3 Show portfolio examples
- [ ] 6.2.4 Show "Learn more" flow
- [ ] 6.2.5 Edit and publish video

**Estimated Time:** 1-2 hours
**Dependencies:** Task 5.4 complete
**Deliverable:** Demo video

### Task 6.3: Gather Initial Feedback
- [ ] 6.3.1 Share with test users (students)
- [ ] 6.3.2 Collect feedback on usefulness
- [ ] 6.3.3 Collect feedback on UI/UX
- [ ] 6.3.4 Identify issues or improvements
- [ ] 6.3.5 Create follow-up tasks based on feedback

**Estimated Time:** Ongoing (1 week)
**Dependencies:** Task 5.4 complete
**Deliverable:** Feedback report and improvement backlog

## Summary

**Total Estimated Time:** 40-55 hours

**Critical Path:**
1. Data Preparation (Phase 1) → 7-10 hours
2. Backend Implementation (Phase 2) → 12-17 hours
3. UI Implementation (Phase 3) → 10-14 hours
4. Integration & Testing (Phase 4) → 7-11 hours
5. Deployment (Phase 5) → 3-5 hours
6. Documentation (Phase 6) → 3-5 hours

**Parallel Work Opportunities:**
- Phase 1 and Phase 3 can start simultaneously
- Task 2.1-2.5 can be worked on in parallel by different developers
- Task 3.1-3.2 can be worked on while Phase 2 is in progress

**Key Milestones:**
- ✓ Data prepared and uploaded to S3
- ✓ Backend generates cards successfully
- ✓ UI displays cards correctly
- ✓ End-to-end flow works
- ✓ Deployed to production
- ✓ User feedback collected

**Dependencies:**
- Affinity map must exist
- Bedrock Knowledge Base must be set up
- Portfolio images must be in S3
- Lecture transcripts must be available
