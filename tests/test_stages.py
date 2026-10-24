"""codex generated tests so may not be exhaustive"""

import unittest
from itertools import product

from wisteria_model_fl import ProcessingElement, VertexState, stages


def vertex(index, **changes):
    u = VertexState(index, changes.pop("defect", False))
    for name, value in changes.items():
        setattr(u, name, value)
    return u


class StageTests(unittest.TestCase):
    def test_three_defects_remain_active_after_merging_and_syncing(self):
        # Three defects leave odd parity at the root, which activates the whole chain during sync.
        root_pe, mid_pe, leaf_pe = [
            ProcessingElement.from_syndrome(i, True, 2) for i in range(3)
        ]
        root, middle, leaf = root_pe.vertex, mid_pe.vertex, leaf_pe.vertex
        for pe in (root_pe, mid_pe, leaf_pe):
            pe.grow()
        # Both edges in this chain now have total radius 2.
        stages.merge(leaf_pe.vertex, [middle])
        stages.merge(mid_pe.vertex, [root, leaf])
        stages.merge(root_pe.vertex, [middle])
        self.assertEqual((root.parity, middle.parity, leaf.parity),
                         (True, False, False))
        for u in (root, middle, leaf):
            u.busy = False
        stages.merge(leaf_pe.vertex, [middle])
        self.assertEqual((root.cindex, middle.cindex, leaf.cindex), (0, 0, 0))
        self.assertIs(middle.parent, root)
        self.assertIs(leaf.parent, middle)
        leaf.busy = False
        for pe, neighbors in [(root_pe, [middle]), (mid_pe, [root, leaf]),
                               (leaf_pe, [middle])]:
            stages.merge(pe.vertex, neighbors)
        self.assertFalse(any(u.busy for u in (root, middle, leaf)))
        for pe in (root_pe, mid_pe, leaf_pe):
            pe.pick()
        self.assertEqual((root.active, middle.active, leaf.active),
                         (True, False, False))
        stages.sync(leaf_pe.vertex, [middle])
        stages.sync(mid_pe.vertex, [root, leaf])
        self.assertFalse(leaf.active)
        stages.sync(leaf_pe.vertex, [middle])
        for pe, neighbors in [(root_pe, [middle]), (mid_pe, [root, leaf]),
                               (leaf_pe, [middle])]:
            stages.sync(pe.vertex, neighbors)
        self.assertTrue(all(u.active for u in (root, middle, leaf)))
        self.assertFalse(any(u.busy for u in (root, middle, leaf)))

    def test_constructing_a_second_pe_does_not_change_the_first(self):
        # Each PE owns a separate vertex; constructing and changing one must not affect another.
        first = ProcessingElement.from_syndrome(2, True, 2)
        before = vars(first.vertex).copy()
        second = ProcessingElement.from_syndrome(3, False, 4)
        second.vertex.radius = 3
        self.assertEqual(vars(first.vertex), before)
        self.assertIsNot(first.vertex, second.vertex)
        self.assertIs(second.vertex.parent, second.vertex)

    def test_growth_changes_only_radius(self):
        # Check growth limits and verify that all fields except radius stay unchanged.
        # The inclusive limit is intentional: radius 2 can grow to 3.
        cases = [(True, 0, 2, 1), (True, 1, 2, 2), (True, 2, 2, 3),
                 (True, 3, 2, 3), (False, 0, 2, 0), (False, 2, 2, 2),
                 (True, 0, 0, 1), (True, 1, 0, 1), (True, 4, 5, 5)]
        for active, radius, w_max, expected_radius in cases:
            with self.subTest(active=active, radius=radius, w_max=w_max):
                u = vertex(4, active=active, radius=radius, busy=True)
                expected = vars(u).copy()
                expected['radius'] = expected_radius
                pe = ProcessingElement(u, w_max)
                pe.grow()
                self.assertEqual(vars(u), expected)
                self.assertEqual(pe.w_max, w_max)

    def test_even_vertex_reparents_without_changing_neighbor(self):
        # Adopting a lower cluster ID with even parity must not write to the new parent.
        u = vertex(8, radius=2, active=True)
        v = vertex(6, cindex=1, parity=True, busy=False)
        expected = vars(u).copy()
        expected.update(cindex=1, parent=v, busy=True)
        neighbor_before = vars(v).copy()
        stages.merge(u, [v])
        self.assertEqual(vars(u), expected)
        self.assertEqual(vars(v), neighbor_before)

    def test_merge_with_only_higher_cluster_is_a_noop(self):
        # An odd root keeps its state when no neighbor offers a lower cluster ID.
        u, v = vertex(1, parity=True), vertex(5, parity=True)
        before = [vars(x).copy() for x in (u, v)]
        stages.merge(u, [v])
        self.assertEqual([vars(x) for x in (u, v)], before)

    def test_equal_cluster_neighbors_keep_the_first_selected_parent(self):
        # Equal cluster IDs do not replace the parent selected earlier in the loop.
        u = vertex(8)
        v, w = vertex(3, cindex=1), vertex(4, cindex=1)
        stages.merge(u, [v, w])
        self.assertIs(u.parent, v)
        self.assertEqual(u.cindex, 1)

    def test_parity_moves_to_new_parent_instead_of_old_parent(self):
        # Reparenting happens before parity transfer for the current neighbor.
        old_parent, v = vertex(4), vertex(1)
        u = vertex(8, cindex=4, parent=old_parent, parity=True)
        old_before = vars(old_parent).copy()
        stages.merge(u, [v, old_parent])
        self.assertIs(u.parent, v)
        self.assertTrue(v.parity)
        self.assertFalse(u.parity)
        self.assertEqual(vars(old_parent), old_before)

    def test_repeated_merge_does_not_transfer_the_same_parity_twice(self):
        # After parity has moved, another merge must neither flip it again nor set busy.
        u, v = vertex(2, parity=True), vertex(0)
        pe = ProcessingElement(u, 2)
        stages.merge(pe.vertex, [v])
        self.assertTrue(v.parity)
        u.busy = False
        before = [vars(x).copy() for x in (u, v)]
        stages.merge(pe.vertex, [v])
        self.assertEqual([vars(x) for x in (u, v)], before)

    def test_two_children_cancel_at_their_parent(self):
        # Two odd children flip the parent twice, leaving all three parities even.
        root = vertex(0)
        u, v = vertex(1, parity=True), vertex(2, parity=True)
        stages.merge(u, [root])
        self.assertTrue(root.parity)
        stages.merge(ProcessingElement(v, 2).vertex, [root])
        self.assertFalse(root.parity or u.parity or v.parity)
        self.assertFalse(root.busy)

    def test_parity_takes_another_pass_when_parent_runs_before_child(self):
        # A parent that already ran forwards newly received parity on its next call.
        root = vertex(0)
        middle = vertex(1, cindex=0, parent=root)
        leaf = vertex(2, cindex=0, parent=middle, parity=True)
        mid_pe, leaf_pe = ProcessingElement(middle, 2), ProcessingElement(leaf, 2)
        stages.merge(mid_pe.vertex, [root, leaf])
        stages.merge(leaf_pe.vertex, [middle])
        self.assertEqual((root.parity, middle.parity, leaf.parity),
                         (False, True, False))
        stages.merge(mid_pe.vertex, [root, leaf])
        self.assertEqual((root.parity, middle.parity, leaf.parity),
                         (True, False, False))

    def test_reversing_neighbors_changes_first_parity_recipient(self):
        # Compare both neighbor orders: the final parent matches, but the first parity recipient differs.
        # These expectations describe our sequential calls, not a paper-mandated order.
        for reverse, expected_recipient in [(False, 3), (True, 1)]:
            with self.subTest(reverse=reverse):
                u, v, w = vertex(5, parity=True), vertex(3), vertex(1)
                neighbors = [w, v] if reverse else [v, w]
                stages.merge(u, neighbors)
                self.assertIs(u.parent, w)
                self.assertEqual([x.index for x in (v, w) if x.parity],
                                 [expected_recipient])

    def test_pick_changes_only_activity_for_all_bit_combinations(self):
        # For every parity, activity, and busy combination, picking changes only activity.
        for parity, active, busy in product((False, True), repeat=3):
            with self.subTest(parity=parity, active=active, busy=busy):
                u = vertex(3, parity=parity, active=active, busy=busy)
                expected = vars(u).copy()
                expected['active'] = parity
                ProcessingElement(u, 2).pick()
                self.assertEqual(vars(u), expected)

    def test_sync_truth_table_and_neighbor_preservation(self):
        # Check every local/neighbor activity combination and leave neighbor records untouched.
        # current activity, neighbor activity -> resulting activity, busy
        cases = [(False, False, False, False), (False, True, True, True),
                 (True, False, True, False), (True, True, True, False)]
        for active, neighbor_active, expected_active, expected_busy in cases:
            for busy in (False, True):
                with self.subTest(active=active, neighbor=neighbor_active, busy=busy):
                    u = vertex(1, active=active, busy=busy, parity=True, radius=2)
                    v, w = vertex(2), vertex(3, active=neighbor_active)
                    expected = vars(u).copy()
                    expected.update(active=expected_active, busy=expected_busy)
                    before = [vars(x).copy() for x in (v, w)]
                    stages.sync(u, [v, w])
                    self.assertEqual(vars(u), expected)
                    self.assertEqual([vars(x) for x in (v, w)], before)

    def test_sync_with_no_neighbors_only_clears_busy(self):
        # With no neighbors, sync clears stale busy without changing activity or other fields.
        for active in (False, True):
            with self.subTest(active=active):
                u = vertex(0, active=active, busy=True)
                expected = vars(u).copy()
                expected['busy'] = False
                stages.sync(u, [])
                self.assertEqual(vars(u), expected)

    def test_from_syndrome_initializes_defect_and_nondefect(self):
        # Both syndrome values produce a self-parented root with the expected initial state.
        for defect in (False, True):
            with self.subTest(defect=defect):
                pe = ProcessingElement.from_syndrome(7, defect, 2)
                u = pe.vertex
                self.assertEqual((u.index, u.cindex, u.radius), (7, 7, 0))
                self.assertIs(u.parent, u)
                self.assertIs(u.defect, defect)
                self.assertIs(u.parity, defect)
                self.assertIs(u.active, defect)
                self.assertFalse(u.busy)
                self.assertEqual(pe.w_max, 2)

    def test_two_defects_neutralize_through_stage_kernels(self):
        # Two odd roots merge into an even cluster that stays inactive after picking and syncing.
        first = ProcessingElement.from_syndrome(0, True, 2)
        second = ProcessingElement.from_syndrome(1, True, 2)
        u, v = first.vertex, second.vertex
        first.grow()
        second.grow()
        self.assertEqual(u.radius + v.radius, 2)
        # These kernel checks supply the accessible pair directly.
        stages.merge(first.vertex, [v])
        stages.merge(second.vertex, [u])
        self.assertIs(v.parent, u)
        self.assertFalse(u.parity or v.parity)
        u.busy = v.busy = False
        stages.merge(first.vertex, [v])
        stages.merge(second.vertex, [u])
        self.assertFalse(u.busy or v.busy)
        first.pick()
        second.pick()
        stages.sync(first.vertex, [v])
        stages.sync(second.vertex, [u])
        self.assertFalse(u.active or v.active or u.busy or v.busy)

    def test_growth_inclusive_limit_and_inactive_vertex(self):
        # Growth can reach w_max + 1, then stops; inactive vertices do not grow.
        u = vertex(0, active=True, radius=2, busy=True)
        pe = ProcessingElement(u, 2)
        pe.grow()
        self.assertEqual(u.radius, 3)
        pe.grow()
        self.assertEqual(u.radius, 3)
        self.assertTrue(u.busy)
        u.radius, u.active = 0, False
        pe.grow()
        self.assertEqual(u.radius, 0)

    def test_merge_transfers_to_first_parent_before_later_reparenting(self):
        # Parity stays with the first recipient even if a later neighbor becomes the new parent.
        u = vertex(5, parity=True)
        first, last = vertex(3), vertex(1)
        stages.merge(u, [first, last])
        self.assertEqual(u.cindex, 1)
        self.assertIs(u.parent, last)
        self.assertTrue(first.parity)
        self.assertFalse(last.parity)
        self.assertFalse(u.parity)
        self.assertTrue(u.busy)

    def test_merge_uses_existing_parent_and_cancels_odd_parity(self):
        # An odd child cancels its odd parent even when that parent appears later in the list.
        parent = vertex(0, parity=True)
        u = vertex(2, cindex=0, parent=parent, parity=True)
        stages.merge(u, [vertex(3), parent])
        self.assertFalse(parent.parity)
        self.assertFalse(u.parity)
        self.assertTrue(u.busy)

    def test_merge_equal_cluster_does_not_reparent_or_clear_busy(self):
        # An equal cluster ID changes neither the existing parent nor an already-set busy flag.
        parent = vertex(0)
        u = vertex(2, cindex=0, parent=parent, busy=True)
        stages.merge(u, [vertex(1, cindex=0)])
        self.assertIs(u.parent, parent)
        self.assertTrue(u.busy)

    def test_merge_empty_neighbors_does_not_transfer_parity(self):
        # An empty loop performs no parity transfer, even for an odd non-root vertex.
        u = vertex(2, cindex=0, parent=vertex(0), parity=True)
        stages.merge(u, [])
        self.assertTrue(u.parity)
        self.assertFalse(u.busy)

    def test_merge_parent_reference_need_not_be_in_neighbor_list(self):
        # Parity writes use the stored parent reference, without looking it up in the supplied list.
        parent = vertex(0)
        u = vertex(2, cindex=0, parent=parent, parity=True)
        stages.merge(u, [vertex(3)])
        self.assertTrue(parent.parity)
        self.assertFalse(u.parity)

    def test_root_reference_identity(self):
        # Separate records stay distinct, and a root never transfers parity to itself.
        u, v = vertex(0, parity=True), vertex(0, parity=True)
        self.assertIs(u.parent, u)
        self.assertIs(v.parent, v)
        self.assertIsNot(u, v)
        self.assertNotEqual(u, v)
        stages.merge(u, [vertex(1)])
        self.assertTrue(u.parity)
        self.assertIs(u.parent, u)

    def test_pick_uses_parity_even_for_nonroot(self):
        # Picking reads parity directly without requiring the vertex to be a root.
        u = vertex(2, parent=vertex(0), parity=True, busy=True)
        pe = ProcessingElement(u, 2)
        pe.pick()
        self.assertTrue(u.active)
        u.parity = False
        pe.pick()
        self.assertFalse(u.active)
        self.assertTrue(u.busy)

    def test_sync_propagates_then_settles_without_deactivating(self):
        # Activity spreads along a chain; later sync calls clear busy but keep vertices active.
        root, middle, leaf = vertex(0, active=True), vertex(1), vertex(2)
        mid_pe, leaf_pe = ProcessingElement(middle, 2), ProcessingElement(leaf, 2)
        stages.sync(leaf_pe.vertex, [middle])
        self.assertFalse(leaf.active)
        stages.sync(mid_pe.vertex, [root, leaf])
        self.assertTrue(middle.active and middle.busy)
        stages.sync(leaf_pe.vertex, [middle])
        self.assertTrue(leaf.active and leaf.busy)
        stages.sync(leaf_pe.vertex, [middle])
        self.assertFalse(leaf.busy)
        stages.sync(leaf_pe.vertex, [])
        self.assertTrue(leaf.active)
        self.assertFalse(leaf.busy)

    def test_sync_clears_stale_busy_without_active_neighbors(self):
        # An inactive vertex with only inactive neighbors clears busy and remains inactive.
        u = vertex(0, busy=True)
        stages.sync(u, [vertex(1)])
        self.assertFalse(u.active)
        self.assertFalse(u.busy)


if __name__ == "__main__":
    unittest.main()
