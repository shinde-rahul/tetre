from nltk import Tree
from tree import TreeNode, FullSentence


def to_nltk_tree_general(node, attr_list=("dep_", "pos_"), level=99999):
    """Tranforms a Spacy dependency tree into an NLTK tree, with certain spacy tree node attributes serving
    as parts of the NLTK tree node label content for uniqueness.

    Args:
        node: The starting node from the tree in which the transformation will occur.
        attr_list: Which attributes from the Spacy nodes will be included in the NLTK node label.
        level: The maximum depth of the tree.

    Returns:
        A NLTK Tree (nltk.tree)
    """

    # transforms attributes in a node representation
    value_list = [getattr(node, attr) for attr in attr_list]
    node_representation = "/".join(value_list)

    if level == 0:
        return node_representation

    if node.n_lefts + node.n_rights > 0:
        return Tree(node_representation, [to_nltk_tree_general(child, attr_list, level-1) for child in node.children])
    else:
        return node_representation


def to_nltk_tree(node):
    """Creates a fixed representation of a Spacy dependency tree as a NLTK tree. This fixed representation
    will be formed by the Spacy's node attributes: dep_, orth_ and pos_.

    Args:
        node: The starting node from the tree in which the transformation will occur.

    Returns:
        A NLTK Tree (nltk.tree)
    """
    if node.n_lefts + node.n_rights > 0:
        return Tree(node.dep_+"/"+node.orth_+"/"+node.pos_, [to_nltk_tree(child) for child in node.children])
    else:
        return node.dep_+"/"+node.orth_+"/"+node.pos_


def print_tree(sent):
    """Prints a Spacy tree by transforming it in an NLTK tree and using its pretty_print method.
    """
    to_nltk_tree(sent.root).pretty_print()


def group_sorting(groups):
    """Given a group (dictionary) re-orders it as a list in which the group with more elements
    of the "sentences" key is at the beginning of this list.

    Returns:
        A list contaning groups with more sentences at the beginning.
    """
    if isinstance(groups, dict):
        groups = list(groups.values())

    newlist = sorted(groups, key=lambda x: len(x["sentences"]), reverse=True)

    return newlist


def get_node_representation(tetre_format, token):
    """Given a format and a SpaCy node (spacy.token), returns this node representation using the NLTK tree (nltk.tree).
    It recursivelly builds a NLTK tree and returns it, not only the node itself.

    Args:
        tetre_format: The attributes of this node that will be part of its string representation.
        token: The SpaCy node itself (spacy.token).

    Returns:
        A NLTK Tree (nltk.tree)
    """

    params = tetre_format.split(",")
    node_representation = token.pos_

    if token.n_lefts + token.n_rights > 0:
        tree = Tree(node_representation,
                    [to_nltk_tree_general(child, attr_list=params, level=0) for child in token.children])
    else:
        tree = Tree(node_representation, [])

    return tree


def get_token_representation(tetre_format, token):
    """Given a format and a SpaCy node (spacy.token), returns this node representation using the NLTK tree (nltk.tree).

    Args:
        tetre_format: The attributes of this node that will be part of its string representation.
        token: The SpaCy node itself (spacy.token).

    Returns:
        A string with the representation.
    """

    string_representation = []
    params = tetre_format.split(",")
    for param in params:
        string_representation.append(getattr(token, param))

    return "/".join(string_representation)


def spacynode_to_treenode(spacy_token, parent=None, root=None):
    """Transforms a SpaCy node (spacy.token) in a Treenode. A Treenode is a pickable version of a SpaCy token parsed
    tree. Both parent and root parameters are only used internally, and should not be passed by the caller.

    Args:
        spacy_token: The SpaCy node itself (spacy.token).
        parent: The Treenode node parent, if exists (Treenode). This is needed so references are maintained accross the
            tree as to make traversing possible.
        root: The Treenode root node, if exists (Treenode). This is needed so references are maintained accross the
            tree as to make traversing possible.

    Returns:
        A Treenode pickable copy of the original SpaCy tree.
    """

    # if further attributes are needed on the copied version, this constructor will need change
    node = TreeNode(spacy_token.dep_, spacy_token.pos_, spacy_token.orth_,
                    spacy_token.idx, spacy_token.n_lefts, spacy_token.n_rights)

    if isinstance(parent, TreeNode):
        node.set_head(parent)
    elif parent is None:
        node.set_is_root()
    else:
        raise ValueError('Unsupported parent node provided to spacy_to_tree2 method')

    if isinstance(root, TreeNode):
        node.set_root(root)
    elif root is None:
        root = node
        node.set_is_root()
    else:
        raise ValueError('Unsupported root node provided to spacy_to_tree2 method')

    for child in spacy_token.children:
        node.add_child(spacynode_to_treenode(child, node, root))

    return node


def spacysentence_to_fullsentence(spacy_sentence, file_id, sentence_id):
    """Transforms a SpaCy span (spacy.span) in a FullSentence object. A FullSentence is a pickable version of a SpaCy
    span parsed tree. All parameters should be sent by the caller.

    A FullSentence is also traversable layer of a Treenode tree, in which the nodes are yielded in their original order,
    as they appeared in the original unparsed sentence.

    Args:
        spacy_sentence: The SpaCy node itself (spacy.span).
        file_id: A number identifyng the file being processed. It is expected to be stable
            (e.g.: same file always receives same id).
        sentence_id: A number identifyng the sentence being processed. It is expected to be stable
            (e.g.: same sentence always receives same id).

    Returns:
        A FullSentence pickable copy of the original SpaCy span (spacy.span).
    """
    tree_node = spacynode_to_treenode(spacy_sentence.root)
    sentence = FullSentence(tree_node, file_id, sentence_id)
    sentence.set_string_representation(str(spacy_sentence))

    return sentence


def nltk_tree_to_qtree(tree):
    """Transforms a NLTK Tree in a QTREE. A QTREE is a string representation of a tree.

    For details, please see: http://www.ling.upenn.edu/advice/latex/qtree/qtreenotes.pdf

    Args:
        tree: The NLTK Tree (nltk.tree).

    Returns:
        A string with the QTREE representation of the NLTK Tree (nltk.tree).
    """
    self_result = " [ "

    if isinstance(tree, Tree):
        self_result += " " + tree.label() + " "

        if len(tree) > 0:
            self_result += " ".join([nltk_tree_to_qtree(node) for node in sorted(tree)])

    else:
        self_result += " " + str(tree) + " "

    self_result += " ] "

    return self_result


def find_in_spacynode(node, dep, orth):
    """Given certain parameters (dep and orth) and a SpaCy or Treenode tree, returns the node in this tree
    that matches the parameters.

    Args:
        node: The Spacy token (spacy.token) or Treenode tree.
        dep: The dependency tag of the node being searched.
        orth: The tokenized orthography of the node being searched.

    Returns:
        False if nothing is found. Or the Spacy token (spacy.token) or Treenode tree if found.
    """

    if dep != "" and orth != "":
        if dep in node.dep_ and orth == node.orth_:
            return node
    elif orth != "":
        if orth == node.orth_:
            return node
    elif dep != "":
        if dep in node.dep_:
            return node

    if len(node.children) > 0:
        results = []
        for child in node.children:
            results.append(find_in_spacynode(child, dep, orth))
        for result in results:
            if result:
                return result

    return False 


def merge_nodes(nodes, under=False):
    """Given 1 or more nodes in a list, merges them under a same new root node.

    Args:
        nodes: A list of the nodes to be merged.
        under: The parent in which these nodes will be merged under (will be children of). If the parameter is a
            False boolean, a new TreeNode parent is created as part of this function.

    Returns:
        The new Treenode parent which children contains the original nodes passed as parameter to this function.
    """

    idx = 0
    n_lefts = 0
    n_rights = 0

    for node in nodes:
        idx += node.idx
        n_lefts += node.n_lefts
        n_rights += node.n_rights

    if not under:
        under = TreeNode(nodes[0].dep_, "", "",
                         idx // len(nodes),
                         n_lefts,
                         n_rights)

    for node in nodes:
        under.children.append(node)
        node.head = under

    return under
