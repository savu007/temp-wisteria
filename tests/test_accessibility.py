"""more codex written tests, not exhaustive probably"""
import unittest

from wisteria_model_fl import ProcessingElement, VertexState


class AccessibilityTests(unittest.TestCase):
    def test_connection_shares_edge_and_vertex_references(self):
        # Connecting two vertices shares one edge in both directions and leaves other vertices alone.
        u, v, isolated = [VertexState(i, False) for i in range(3)]
        edge = u.connect(v)
        self.assertIs(u.neighbors[v], edge)
        self.assertIs(v.neighbors[u], edge)
        self.assertEqual(edge.weight, 2)
        self.assertFalse(edge.pregrown)
        self.assertEqual(isolated.neighbors, {})

    def test_radius_threshold_uses_both_endpoints(self):
        # Check below, at, and above the weight threshold without changing either vertex.
        u, v = VertexState(0, False), VertexState(1, False)
        u.connect(v, weight=5)
        first, second = ProcessingElement(u, 5), ProcessingElement(v, 5)
        for radius_u, radius_v, expected in [(0, 0, []), (2, 2, []),
                                             (2, 3, [v]), (4, 3, [v])]:
            with self.subTest(radii=(radius_u, radius_v)):
                u.radius, v.radius = radius_u, radius_v
                before = [vars(x).copy() for x in (u, v)]
                self.assertEqual(first.accessible_neighbors, expected)
                self.assertEqual(second.accessible_neighbors, [u] if expected else [])
                self.assertEqual([vars(x) for x in (u, v)], before)

    def test_pregrown_edge_is_accessible_with_zero_radii(self):
        # Pregrowth bypasses the radius check; removing it restores the normal threshold.
        u, v = VertexState(0, False), VertexState(1, False)
        edge = u.connect(v, weight=6, pregrown=True)
        pe = ProcessingElement(u, 6)
        self.assertEqual(pe.accessible_neighbors, [v])
        edge.pregrown = False
        self.assertEqual(pe.accessible_neighbors, [])
        self.assertEqual((u.radius, v.radius, edge.weight), (0, 0, 6))

    def test_edge_updates_are_visible_from_both_endpoints(self):
        # Both PEs see changes to the shared weight and pregrown flag on the next lookup.
        u, v = VertexState(0, False), VertexState(1, False)
        edge = u.connect(v, weight=4)
        u.radius = v.radius = 1
        first, second = ProcessingElement(u, 4), ProcessingElement(v, 4)
        self.assertEqual(first.accessible_neighbors, [])
        edge.weight = 2
        self.assertEqual(first.accessible_neighbors, [v])
        self.assertEqual(second.accessible_neighbors, [u])
        edge.weight = 4
        edge.pregrown = True
        self.assertEqual(first.accessible_neighbors, [v])
        self.assertEqual(second.accessible_neighbors, [u])

    def test_filter_preserves_connection_order(self):
        # Filtering out a blocked edge must preserve the order of the remaining neighbors.
        u = VertexState(5, False)
        v, blocked, w = [VertexState(i, False) for i in (3, 0, 1)]
        u.connect(v, pregrown=True)
        u.connect(blocked)
        u.connect(w, pregrown=True)
        self.assertEqual(ProcessingElement(u, 2).accessible_neighbors, [v, w])

    def test_merge_ignores_inaccessible_lower_cluster(self):
        # A blocked neighbor cannot become the parent, even when its cluster ID is smallest.
        u = VertexState(5, True)
        blocked, v = VertexState(0, True), VertexState(2, False)
        u.connect(blocked)
        u.connect(v, pregrown=True)
        before = vars(blocked).copy()
        ProcessingElement(u, 2).merge()
        self.assertEqual(u.cindex, 2)
        self.assertIs(u.parent, v)
        self.assertTrue(v.parity)
        self.assertFalse(u.parity)
        self.assertEqual(vars(blocked), before)

    def test_sync_ignores_active_neighbor_until_edge_becomes_accessible(self):
        # Activity crosses the edge only after the neighbor grows enough to reach its weight.
        u, v = VertexState(0, False), VertexState(1, True)
        u.connect(v)
        pe, neighbor_pe = ProcessingElement(u, 2), ProcessingElement(v, 2)
        pe.sync()
        self.assertFalse(u.active or u.busy)
        neighbor_pe.grow()
        pe.sync()
        self.assertFalse(u.active or u.busy)
        neighbor_pe.grow()
        pe.sync()
        self.assertTrue(u.active and u.busy)
        pe.sync()
        self.assertTrue(u.active)
        self.assertFalse(u.busy)

    def test_pregrown_update_enables_sync_without_growth(self):
        # Turning on pregrowth lets activity propagate while both radii remain zero.
        u, v = VertexState(0, False), VertexState(1, True)
        edge = u.connect(v)
        pe = ProcessingElement(u, 2)
        pe.sync()
        self.assertFalse(u.active)
        edge.pregrown = True
        pe.sync()
        self.assertTrue(u.active and u.busy)
        self.assertEqual((u.radius, v.radius), (0, 0))

    def test_two_defects_merge_only_after_growth_reaches_edge_weight(self):
        # Exercise the PE through growth, parity cancellation, and an inactive final cluster.
        first = ProcessingElement.from_syndrome(0, True, 2)
        second = ProcessingElement.from_syndrome(1, True, 2)
        u, v = first.vertex, second.vertex
        u.connect(v)
        second.merge()
        self.assertIs(v.parent, v)
        self.assertTrue(u.parity and v.parity)
        first.grow()
        second.merge()
        self.assertIs(v.parent, v)
        second.grow()
        second.merge()
        self.assertIs(v.parent, u)
        self.assertFalse(u.parity or v.parity)
        u.busy = v.busy = False
        first.merge()
        second.merge()
        self.assertFalse(u.busy or v.busy)
        first.pick()
        second.pick()
        first.sync()
        second.sync()
        self.assertFalse(u.active or v.active)

    def test_isolated_vertex_has_no_accessible_neighbors(self):
        # Merge and sync leave an isolated active root unchanged.
        pe = ProcessingElement.from_syndrome(0, True, 2)
        before = vars(pe.vertex).copy()
        self.assertEqual(pe.accessible_neighbors, [])
        pe.merge()
        pe.sync()
        self.assertEqual(vars(pe.vertex), before)


if __name__ == "__main__":
    unittest.main()
