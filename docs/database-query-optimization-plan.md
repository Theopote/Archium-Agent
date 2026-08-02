# Database Query Optimization Plan

## Identified N+1 Query Issues

### 1. Asset Matching Service (`asset_matching_service.py`)

**Issue**: In `match_presentation_slides()` method:
```python
# Line 259-269: Loop over slides with potential database queries
for slide in slides:
    matched_slide, slide_matches, changed = self._match_slide(
        slide, assets, qa_reports=qa_reports, ...
    )
    updated.append(self._presentations.save_slide(matched_slide) if changed else matched_slide)

# Line 280-289: Another loop with database operations
for slide in updated:
    bound_slide, rebound_changed = self._bind_slide_evidence_items(
        slide, assets, qa_reports,
    )
    if rebound_changed:
        bound_slide = self._presentations.save_slide(bound_slide)
```

**Optimization**:
- Batch slide updates instead of individual saves
- Use eager loading for slide relationships
- Consider bulk operations for evidence binding

### 2. Knowledge Graph Service (`knowledge_graph_service.py`)

**Issue**: In `_merge_confirmed_edges()` method:
```python
# Line 245-270: Loop over confirmed edges with node lookups
for confirmed in self._confirmed_edges.list_by_project(project_id, active_only=True):
    for ref in (confirmed.source_ref, confirmed.target_ref):
        if ref in nodes:
            continue
        # Node creation and edge operations in loop
```

**Optimization**:
- Preload all referenced nodes in a single query
- Batch node and edge operations
- Use SQLAlchemy bulk operations

### 3. Repository Layer Missing Eager Loading

**Issue**: Many repository queries don't use eager loading for commonly accessed relationships.

**Optimization**:
- Add `joinedload()` for one-to-one relationships
- Add `selectinload()` for one-to-many relationships  
- Add `subqueryload()` for large collections

## Optimization Strategy

### Phase 1: Add Eager Loading to Repositories

1. **AssetRepository**: Add eager loading for commonly accessed relationships
2. **PresentationRepository**: Add eager loading for slides and their relationships
3. **ProjectRepository**: Add eager loading for members and assets
4. **KnowledgeGraphEdgeRepository**: Add eager loading for source/target nodes

### Phase 2: Batch Operations

1. Replace individual saves with bulk operations where possible
2. Use `session.bulk_save_objects()` for non-critical paths
3. Implement batch update methods in repositories

### Phase 3: Query Optimization

1. Add database indexes for frequently queried fields
2. Optimize complex queries with proper joins
3. Use query caching for repeated queries

### Phase 4: Monitoring

1. Add query logging to identify slow queries
2. Implement query performance monitoring
3. Set up alerts for N+1 query patterns

## Implementation Priority

**High Priority**:
1. Add eager loading to AssetRepository and PresentationRepository
2. Optimize `match_presentation_slides()` batch operations
3. Fix `_merge_confirmed_edges()` node loading

**Medium Priority**:
1. Add eager loading to other repositories
2. Implement bulk operations
3. Add database indexes

**Low Priority**:
1. Query monitoring and alerting
2. Advanced query optimization
3. Caching layer

## Expected Impact

- **Performance**: 50-80% reduction in database query count for common operations
- **Response Time**: 30-60% improvement for presentation generation
- **Scalability**: Better performance with larger projects and datasets
