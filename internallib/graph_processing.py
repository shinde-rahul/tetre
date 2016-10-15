from nltk import Tree
from types import FunctionType
from internallib.dependency_helpers import *
from internallib.rule_applier import *
from internallib.tree_utils import find_in_spacynode, merge_nodes
import inspect
from functools import wraps, reduce
import sys

class Growth(RuleApplier):
    def __init__(self):
        RuleApplier.__init__(self)
        self.subs = ['nsubj', 'csubj', 'nsubjpass', 'csubjpass']
        self.objs = ['dobj', 'iobj', 'pobj']
        self.move_if = [("xcomp", "obj"), ("ccomp", "obj"), ("xcomp", "subj"), ("ccomp", "subj")]
        self.downwards_subj = "nsubj"

    @RuleApplier.register_function
    def replace_subj_if_dep_is_relcl_or_ccomp(self, root, node_set, spacy_tree):
        """
            1) Consider the following sentence:
            "2 Related work Learning to rank has been a promising research area which continuously improves web search relevance (Burges et al."

            The dependency parser puts not the action the improves something as a parent of the word "improves" in the in the tree, and adds to it the relcl relation.
            This method adjusts the tree, bringing the node above under "improves".


            2) Consider the following sentence:
            "The best known recovery algorithm for dirty mapping entries, proposed in LazyFTL, exhibits two shortcomings that GeckoFTL improves upon."

            In this case, GeckoFTL is is a proper noun, so it shouldn't be replaced.
        """

        isApplied = False

        upwards = ["relcl", "ccomp"]

        #adjust tree
        token = spacy_tree
        token_head = spacy_tree

        # print("0", token.to_tree_string())
        # print("0", token_head.to_tree_string())

        if (token_head.dep_ in upwards and token_head.head != token):
            token_head = token_head.head

            # print("1", token.to_tree_string())
            # print("1", token_head.to_tree_string())

            isChangingPossibilities = []
            isChanging = False
            hasSubj = False

            children_list = token.children[:]
            for i in range(0, len(children_list)):
                if (children_list[i].dep_ in self.subs):
                    hasSubj = True

                    # print(token.children[i].orth_, token.children[i].pos_)
                    
                    if not (token.children[i].pos_ in ["NOUN", "PROPN", "VERB", "NUM", "PRON", "X"]):
                        token.children.pop(i)
                        isChangingPossibilities.append(True)
                    else:
                        isChangingPossibilities.append(False)

                    # print(isChanging)
                    # print()

            if True in isChangingPossibilities:
                isChanging = True

            if not hasSubj:
                isChanging = True

            # print(isChanging)
            # print()

            # print("2", hasSubj)
            # print("2", isChanging)
            # print("2", token.to_tree_string())
            # print("2", token_head.to_tree_string())

            if (isChanging):
                isApplied = True
                children_list = token_head.children[:]
                for i in range(0, len(children_list)):
                    if (children_list[i].idx == token.idx):
                        token_head.children.pop(i)

                        #adjust representation
                        node_set.append(self.downwards_subj)

                # print("3", token.to_tree_string())
                # print("3", token_head.to_tree_string())

                # print("---------------")

                token_head.dep_ = self.downwards_subj
                token.children.append(token_head)
                token_head.head = token

        return root, node_set, spacy_tree, isApplied

    @RuleApplier.register_function
    def recurse_on_dep_conj_if_no_subj(self, root, node_set, spacy_tree):
        """
            1) Consider the following sentence:
            "Using many ASR hypotheses helps recover the ASR errors of NE words in 1-best ASR results and improves NER accuracy."

            The dependency parser puts not the action the improves something as a parent of the word "improves" in the in the tree, and adds to it the conj relation.
            This method adjusts the tree, bringing the node above under "improves".

            
            2) Now consider the following sentence:
            "Both identify product features from reviews, but OPINE significantly improves on both."

            Note how, although improves is a conj, "Both" is the subj up the tree. However, there is a "but" as the "cc", and beucase of this we need to pick the "conj" below instead of the "subj".

            3) Now consider:
            "SFS [6] (sort-filter-skyline) is based on the same rationale as BNL , but improves performance by first sorting the data according to a monotone function."

            This has a "but", however no other conj, in this case we should use the nsubj again.

            4) Now consider:
            "[16] studies the usage of grammars and LZ77 parsing for compression of similar sequence collections and improves complexity bounds with respect to space as well as time."

            The subj is actually the dobj of the head
        """

        isApplied = False

        upwards = ["conj"]

        token = spacy_tree
        token_head = spacy_tree

        while True:

            if (token_head.dep_ in upwards        \
                and token_head.head != token_head \
                and len([child for child in token.children if child.dep_ in self.subs]) == 0):

                # print("pre1", token_head)
                
                token_head = token_head.head

                # print("pre2", token_head)

                # needs_loop = True
                # while needs_loop:

                changed = False
                children_list = token_head.children[:]

                isBut           = False
                otherConjExists = False
                hasSubj         = False
                hasObj          = False

                for j in range(0, len(children_list)):
                    if token_head.children[j].dep_ in "cc" \
                        and token_head.children[j].orth_ == "but":
                        isBut = True
                    if token_head.children[j].dep_ in "conj" \
                        and token_head.children[j] != token:
                        otherConjExists = True
                    if "subj" in token_head.children[j].dep_:
                        hasSubj = True
                    if "obj" in token_head.children[j].dep_:
                        hasObj = True

                for i in range(0, len(children_list)):

                    # print()
                    # print("0", isBut)
                    # print("0", token_head.children[i].dep_)
                    # print("0", token_head.children[i].orth_)
                    # print("0", token.orth_)

                    isOtherConj = token_head.children[i].dep_ == "conj" and token_head.children[i] != token
                    isSubj = token_head.children[i].dep_ in self.subs
                    isObj = token_head.children[i].dep_ in self.objs

                    nodeResult = find_in_spacynode(token_head.children[i], token.dep_, token.orth_)
                    if nodeResult != False:
                        isSubChild = True
                    else:
                        isSubChild = False

                    cond_subj = not isBut and isSubj
                    cond_dobj = not isBut and not hasSubj and isObj
                    cond_conj_other = isBut and not isSubj and otherConjExists and isOtherConj and not isSubChild
                    cond_conj_same  = isBut and not otherConjExists and isSubj

                    # print("1", isOtherConj)
                    # print("1", cond_subj)
                    # print("1", cond_conj_other)
                    # print("1", cond_conj_same)
                    # print("1", isBut)

                    if  (cond_subj) or \
                        (cond_conj_other) or \
                        (cond_dobj) or \
                        (cond_conj_same):

                        isApplied = True

                        # print("2", token.to_tree_string())
                        # print("2", token_head.to_tree_string())
                        # print("2", token_head.children[i].to_tree_string())
                        # print("2", node_set)
                        # print("2", isBut)

                        if cond_dobj or cond_conj_other:
                            token_head.children[i].dep_ = self.downwards_subj

                        # adjust representation
                        node_set.append(token_head.children[i].dep_ )

                        #adjust actual tree
                        token.children.append(token_head.children[i])
                        token_head.children[i].head = token
                        token_head.children.pop(i)

                        # print("3", token.to_tree_string())
                        # print("3", token_head.to_tree_string())
                        # print("3", node_set)
                        # print("3", isBut)

                        # print("---------------------------------------------------------------------")
                        # print()

                        changed = True
                        break

                    # if not changed:
                    #     needs_loop = False

            else:
                break

        return root, node_set, spacy_tree, isApplied

    @RuleApplier.register_function
    def transform_xcomp_to_dobj_or_sub_if_doesnt_exists(self, root, node_set, spacy_tree):
        """
            1) Consider the sentence:
            xcomp > "Recent work has showed that structured retrieval improves answer ranking for factoid questions: Bilotti et al."
            ccomp > "The Fat-Btree structure presented in [19] vastly reduces the index-modification cost and improves the dynamic data skew handling method."

            Although it is possible to understand that "structured retrieval" "improves" "answer ranking..." the "answer ranking..." part is
            not presented as a dobj dependency, but a xcomp dependency instead. This rule transforms xcomp into "obj" as both contain the same
            purpose for information extraction.

            2) Consider this sentence:
            ccomp > "2 Related Work Caching frequently accessed data at the client side not only improves the userÃ¢Â€Â™s experience of the distributed system, but also alleviates the serverÃ¢Â€Â™s workload and enhances its scalability."

            Although in this sentence the dobj was detected, the ccomp is the nsubj. Thus, after replacing the items for dobj, if there is no nsubj in the sentence we try to tranform then in nsubj.
        """

        isApplied = False

        should_return = False

        for replace, target in self.move_if:
            is_obj = False

            for child in spacy_tree.children:
                if target in child.dep_:
                    is_obj = True
                    break

            if is_obj:
                continue

            for child in spacy_tree.children:
                if replace in child.dep_:
                    isApplied = True

                    child.dep_ = target
                    node_set = [target if node==replace else node for node in node_set]
                    break

        node_set = set([self.rewrite_dp_tag(node) for node in node_set])
        return root, node_set, spacy_tree, isApplied

    @RuleApplier.register_function
    def transform_prep_in_to_dobj(self, root, node_set, spacy_tree):
        """
            1) Consider the following sentence:
            "While matrix factorization is widely used in recommender systems, matrix co-factorization helps to handle multiple aspects of the data and improves in predicting individual decisions (Hong et al. "

            One can see that "matrix co-factorization" and improves "predicting individual decisions". It could be rewriting as "improves prediction of individual decisions". Thus anything after a "prep in" could be considered an "obj".
        """
        isApplied = False

        target = "obj"
        replace = "prep"

        is_obj = False
        for child in spacy_tree.children:
            if target in child.dep_:
                is_obj = True

        for child in spacy_tree.children:
            if replace in child.dep_ and child.orth_ == "in":
                if not is_obj:
                    isApplied = True

                    child.dep_ = target
                    node_set = [target if node==replace else node for node in node_set]

        node_set = list(set([self.rewrite_dp_tag(node) for node in node_set]))
        return root, node_set, spacy_tree, isApplied

    @RuleApplier.register_function
    def bring_grandchild_prep_or_relcl_up_as_child(self, root, node_set, spacy_tree):
        """
            1) Consider the following sentence:
            "Experiments show that the proposed method improves the performance by 2.9 and 1.6 to 67.3 and 67.2 in F1-measure on the MUC-6 and MUC-7 corpora, respectively, due to much more gain in precision compared with the loss in recall."

            The dependency parser relates the "prep by" relationship to "performance" instead of "improves", causing the dobj part to be too large.

            2) Now consider:
            "(Taskar et al., 2004) suggested a method for maximal margin parsing which employs the dynamic programming approach to decoding and parameter estimation problems."

            This would also bring up prep "to".

            3) Now consider:
            "One method considers the phrases as bag-ofwords and employs a convolution model to transform the word embeddings to phrase embeddings (Collobert et al."
            "(Kobayashi et al., 2004) employs an iterative semi-automatic approach which requires human input at every iteration."
            "The formerÃ¢Â€Â™s precision on the explicit feature extraction task is 22% lower than OPINE Ã¢Â€Â™s while the latter employs an iterative semi-automatic approach which requires significant human input; neither handles implicit features."

            This would also bring up "relcl".

            4) Now consider:
            "It employs a single coherence model based on semantic signatures similar to our coherence objective."

            This would also bring up "acl".

            5) Now consider:
            "The algorithm employs a max-heap H for managing combinations of feature entries in descending order of their combination scores."

            This would also bring up prep "for".

            6) Now consider:
            "SemTag uses the TAP knowledge base5 , and employs the cosine similarity with TF-IDF weighting scheme to compute the match degree between a mention and an entity, achieving an accuracy of around 82%."

            This would also bring up prep "with".

            7) Now consider:
            "QPipe employs a micro-kernel approach whereby functionality of each physical operator is exposed as a separate service."

            This would also bring up prep "whereby".
        """

        bring_up = [
            ("prep", "by", "prep"),
            ("prep", "to", "prep"),
            ("prep", "for", "prep"),
            ("prep", "with", "prep"),
            ("prep", "whereby", "prep"),
            ("relcl", "", "mod"),
            ("acl", "", "mod"),
            ("advcl", "", "mod"),
        ]

        isApplied = False

        for child in spacy_tree.children:

            if  "obj" in child.dep_ or \
                "subj" in child.dep_:

                for dep_, orth_, dep_new_ in bring_up:

                    # print ("0", dep_, orth_, dep_new_)
                
                    changed = True
                    while changed:
                        changed = False

                        prep = find_in_spacynode(child, dep_, orth_)
                        if prep == False:
                            break

                        # print ("1", prep.dep_, prep.orth_, prep.idx)

                        prep_head = prep.head.children[:]

                        for i in range(0, len(prep_head)):

                            # print ("2", prep_head[i].dep_, prep_head[i].orth_, prep_head[i].idx)

                            if prep.dep_ in prep_head[i].dep_ and \
                                prep.orth_ == prep_head[i].orth_ and \
                                prep.idx == prep_head[i].idx:

                                isApplied = True

                                #adjust actual tree
                                prep.head.children.pop(i)
                                spacy_tree.children.append(prep)
                                prep.head = spacy_tree
                                prep.dep_ = dep_new_

                                #adjust representation
                                node_set.append(dep_new_)

                                changed = True
                                break

        return root, node_set, spacy_tree, isApplied

class Reduction(RuleApplier):
    def __init__(self):
        RuleApplier.__init__(self)
        self.tags_to_be_removed = set(['punct', 'mark', ' ', '', 'meta'])

    @RuleApplier.register_function
    def remove_duplicates(self, root, node_set, spacy_tree):
        """
            1) This groups sentence with e.g.: multiple "punct" into the same group for easier analysis.
        """
        return root, set(node_set), spacy_tree, False

    @RuleApplier.register_function
    def remove_tags(self, root, node_set, spacy_tree):
        """
            1) This removes dependency paths of the types contained in self.tags_to_be_removed as they are not considered
            relevant. This reduces the number of different groups.
        """
        isApplied = False

        node_set = set(node_set) - self.tags_to_be_removed

        for child in spacy_tree.children:
            if child.dep_ in self.tags_to_be_removed:
                isApplied = True
                child.nofollow = True

        return root, node_set, spacy_tree, isApplied

    @RuleApplier.register_function
    def transform_tags(self, root, node_set, spacy_tree):
        """
            1) This transform tags from several variations into a more general version. The mappings are contained
            in the self.translation_rules variables.
        """
        node_set = set([self.rewrite_dp_tag(node) for node in node_set])
        return root, node_set, spacy_tree, False

    @RuleApplier.register_function
    def merge_multiple_subj_or_dobj(self, root, node_set, spacy_tree):
        """
            1) Unify multiple subj and fix representation:
            "Another partitional method ORCLUS [2] improves PROCLUS by selecting principal components so that clusters not parallel to the original dimensions can also be detected."

            It has 2 nsubj: "Another partitional method" and "ORCLUS [2]". They should be in the same sentence.
            Because it has 2 subj, the representation ends up being the one from the last nsubj.
        """

        # return root, node_set, spacy_tree, False

        isApplied = False

        groups = ["subj", "obj"]
        
        for group in groups:
            this_group = []

            count = reduce(lambda x, y: x + 1 if group in y.dep_ else x, spacy_tree.children, 0)

            # print("group", group, count)

            if count < 2:
                continue;

            changed = True
            while changed:
                changed = False
                children_list = spacy_tree.children[:]

                for i in range(0, len(children_list)):
                    if group in children_list[i].dep_:
                        this_group.append(children_list[i])
                        spacy_tree.children.pop(i)

                        # print("group", group, count)

                        isApplied = True
                        changed = True
                        break

            child = merge_nodes(this_group)
            spacy_tree.children.append(child)
            child.head = spacy_tree

        return root, node_set, spacy_tree, isApplied

class Process(object):
    def __init__(self):
        self.growth = Growth()
        self.reduction = Reduction()
        return

    def applyAll(self, nltk_tree, spacy_tree):

        # print("will process")

        nltk_tree, applied_growth = self.growth.apply(nltk_tree, spacy_tree)
        nltk_tree, applied_reduction = self.reduction.apply(nltk_tree, spacy_tree)
        return nltk_tree, (applied_growth + applied_reduction)
