"""
Test graph compilation
"""

from agent.graph import build_conversation_graph


def test_graph_compiles():
    """
    Verify that build_conversation_graph() compiles successfully without errors.
    
    This test ensures:
    - The graph structure is valid
    - All nodes are properly connected
    - Conditional edges are correctly configured
    - The graph can be compiled without exceptions
    """
    # Attempt to build and compile the graph
    graph = build_conversation_graph()
    
    # Verify the graph was compiled successfully
    assert graph is not None, "Graph compilation returned None"
    
    # Verify the graph has the expected structure
    # The compiled graph should have a get_graph() method
    assert hasattr(graph, 'invoke'), "Compiled graph missing invoke method"
    assert hasattr(graph, 'ainvoke'), "Compiled graph missing ainvoke method"
    
    print("✓ Graph compiled successfully")
    print(f"✓ Graph type: {type(graph)}")


if __name__ == "__main__":
    test_graph_compiles()
    print("\nAll graph compilation tests passed!")
