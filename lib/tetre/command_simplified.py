from graphviz import Digraph

import json
import copy
import random
import csv
import sys

from django.utils.safestring import mark_safe
from django.template import Template, Context

from tetre.command_utils import setup_django_template_system, percentage
from tetre.command import SentencesAccumulator, ResultsGroupMatcher, GroupImageNameGenerator

from directories import dirs

from tetre.graph_processing import Process, Reduction
from tetre.graph_processing_children import ProcessChildren
from tetre.graph_extraction import ProcessExtraction
from parsers import get_tokens, highlight_word
from tree_utils import group_sorting, get_node_representation


class GroupImageRenderer(object):
    base_image_name = 'command-simplified-group'

    def __init__(self, argv):
        """Generates the images for each group of sentences.

        Args:
            argv: The command line arguments.
        """
        self.argv = argv
        self.current_token_id = 0
        self.current_group_id = 0

    def gen_group_image(self, tree):
        """Generates the images based on the node that represents this group.

        Args:
            tree: The NLTK Tree node.

        Returns:
            A string with the image path.
        """
        e = Digraph(self.argv.tetre_word, format=GroupImageNameGenerator.file_extension)
        e.attr('node', shape='box')

        current_id = self.current_token_id

        try:
            label = tree.label()
        except AttributeError:
            label = str(tree)

        e.node(str(current_id), label)

        current_global_id = {}

        if hasattr(tree, '__iter__'):
            for child in tree:
                self.current_token_id += 1
                current_global_id[str(self.current_token_id)] = child

            for child_id, child in current_global_id.items():
                e.node(child_id, "???")
                e.edge(str(current_id), child_id, label=child)

        name_generator = GroupImageNameGenerator(self.base_image_name, self.argv.tetre_word, str(self.current_group_id))
        e.render(name_generator.get_render_path())

        self.current_group_id += 1

        return name_generator.get_base_path_with_extension()


class OutputGenerator(object):
    def __init__(self, argv, command_simplified_group):
        """Generates the HTML output as to be analysed.

        Args:
            argv: The command line arguments.
            command_simplified_group: the CommandSimplifiedGroup object itself,
                as to access the current groups of sentences.
        """
        self.argv = argv
        self.groups = command_simplified_group.get_groups()
        self.command_simplified_group = command_simplified_group

    def get_extracted_results(self, sentence, template):
        """Generates the HTML/JSON output of the extracted results, given the sentence object.

        Args:
            sentence: A dictionary that describes all data related to the sentence being processed.
            template: The template renderer from Django.

        Returns:
            subj: A string with the content of the subj part of the relation.
            obj: A string with the content of the obj part of the relation.
            others_json or others_html: A string with other possible components of the relation.
        """
        rule = Reduction()

        has_subj = False
        has_obj = False

        subj = ""
        obj = ""
        others_html = ""
        others_json = []

        for results in sentence["rules"]:
            for key, values in results.items():
                dep = rule.rewrite_dp_tag(key)

                for value in values:
                    if dep == 'subj' and not has_subj:
                        subj = value
                        has_subj = True
                    elif dep == 'obj' and not has_obj:
                        obj = value
                        has_obj = True
                    else:
                        if self.argv.tetre_output == "json":
                            others_json.append({"relation": dep, "target": value})
                        elif self.argv.tetre_output == "html":
                            c = Context({"opt": dep, "result": value})
                            others_html += template["template"].render(c)

        if self.argv.tetre_output == "json":
            return subj, obj, others_json
        elif self.argv.tetre_output == "html":
            return subj, obj, others_html

    def get_external_results(self, sentence):
        """Obtains the results and relations extracted by the external tools for comparison purposes. Used
        for evaluation.

        Args:
            sentence: A dictionary that describes all data related to the sentence being processed.

        Returns:
            A string with the HTML for each of the external extracted relations for this sentence.
        """
        filename = self.argv.tetre_word + "-" + str(sentence["sentence"].file_id) \
            + "-" + str(sentence["sentence"].id) + "-" + str(sentence["token"].idx)

        allenai_openie = dirs['output_allenai_openie']['path'] + filename
        stanford_openie = dirs['output_stanford_openie']['path'] + filename
        mpi_clauseie = dirs['output_mpi_clauseie']['path'] + filename

        text_allenai_openie = ""
        text_stanford_openie = ""
        text_mpi_clauseie = ""

        try:
            with open(allenai_openie, 'r') as text_allenai_openie:
                text_allenai_openie = text_allenai_openie.read()
        except IOError:
            pass

        try:
            with open(stanford_openie, 'r') as text_stanford_openie:
                text_stanford_openie = text_stanford_openie.read()
        except IOError:
            pass

        try:
            with open(mpi_clauseie, 'r') as text_mpi_clauseie:
                text_mpi_clauseie = text_mpi_clauseie.read()
        except IOError:
            pass

        return text_allenai_openie.replace('\n', '<br />'),\
            text_stanford_openie.replace('\n', '<br />'),\
            text_mpi_clauseie.replace('\n', '<br />')

    def graph_gen_html_sentence(self, sentence):
        """Merges all parts of the extracted relations of the sentence. Retuns all the output related to
        the sentence being processed.

        Args:
            sentence: A dictionary that describes all data related to the sentence being processed.

        Returns:
            A string with the HTML/JSON for all the output of this sentence.
        """

        with open(dirs['html_templates']['path'] + 'each_sentence.html', 'r') as each_sentence:
            each_sentence = each_sentence.read()

        with open(dirs['html_templates']['path'] + 'each_sentence_opt.html', 'r') as each_sentence_opt:
            each_sentence_opt = each_sentence_opt.read()

        to = Template(each_sentence_opt)

        subj, obj, others = self.get_extracted_results(sentence, {"html": True, "template": to})

        text_allenai_openie = text_stanford_openie = text_mpi_clauseie = ""

        if self.argv.tetre_include_external:
            text_allenai_openie, text_stanford_openie, text_mpi_clauseie = self.get_external_results(sentence)

        ts = Template(each_sentence)
        c = Context({
            "add_external": self.argv.tetre_include_external,
            "gf_id": sentence["sentence"].file_id,
            "gs_id": sentence["sentence"].id,
            "gt_id": sentence["token"].idx,
            "path": sentence["img_path"],
            "sentence": mark_safe(highlight_word(sentence["sentence"], self.argv.tetre_word)),
            "subj": subj,
            "obj": obj,
            "rel": self.argv.tetre_word,
            "others": mark_safe(others),
            "rules_applied": mark_safe(", ".join(sentence["applied"])),
            "text_allenai_openie": mark_safe(highlight_word(text_allenai_openie, self.argv.tetre_word)),
            "text_stanford_openie": mark_safe(highlight_word(text_stanford_openie, self.argv.tetre_word)),
            "text_mpi_clauseie": mark_safe(highlight_word(text_mpi_clauseie, self.argv.tetre_word))
        })

        return ts.render(c)

    def graph_gen_html(self):
        """Generates the HTML output for all the sentences for the word being searched for.
        """
        setup_django_template_system()
        file_name = "results-" + self.argv.tetre_word + ".html"

        with open(dirs['html_templates']['path'] + 'index_group.html', 'r') as index_group:
            index_group = index_group.read()

        with open(dirs['html_templates']['path'] + 'each_img_accumulator.html', 'r') as each_img_accumulator:
            each_img_accumulator = each_img_accumulator.read()

        all_imgs_html = ""
        max_sentences = 0

        for group in group_sorting(self.groups):
            t = Template(each_img_accumulator)
            c = Context({"accumulator_img": group["img"],
                         "total_group_sentences": len(group["sentences"])})
            all_imgs_html += t.render(c)

            each_sentence_html = ""

            if len(group["sentences"]) > max_sentences:
                max_sentences = len(group["sentences"])

            for sentence in group["sentences"]:

                if self.argv.tetre_output_csv:
                    csv_row = [self.argv.tetre_word,
                               str(sentence["sentence"].file_id) + "-" + str(sentence["sentence"].id) + "-" + str(
                                   sentence["token"].idx)]

                    wr = csv.writer(sys.stdout, quoting=csv.QUOTE_ALL)
                    wr.writerow(csv_row)

                each_sentence_html += self.graph_gen_html_sentence(sentence)

            all_imgs_html += each_sentence_html

        avg_per_group = self.command_simplified_group.get_average_per_group()
        max_num_params = self.command_simplified_group.get_max_params()

        t = Template(index_group)
        c = Context({"sentences_num": self.command_simplified_group.get_sentence_totals(),
                     "groups_num": len(self.groups),
                     "max_group_num": max_sentences,
                     "average_per_group": avg_per_group,
                     "all_sentences": mark_safe(all_imgs_html),
                     "max_num_params": max_num_params,
                     "word": self.argv.tetre_word})

        with open(dirs['output_html']['path'] + file_name, 'w') as output:
            output.write(t.render(c))

    def graph_gen_json(self):
        """Generates the JSON output for all the sentences for the word being searched for.
        """
        json_result = []

        for group in group_sorting(self.groups):
            for sentence in group["sentences"]:
                subj, obj, others = self.get_extracted_results(sentence, {"html": False, "template": None})

                json_result.append(
                    {"sentence": str(sentence["sentence"]),
                     "relation": {"rel": self.argv.tetre_word, "subj": subj, "obj": obj},
                     "other_relations": others,
                     "rules_applied": ",".join(sentence["applied"])})

        print(json.dumps(json_result, sort_keys=True))


class CommandSimplifiedGroup(SentencesAccumulator, ResultsGroupMatcher):
    def __init__(self, argv):
        """Generates the HTML for all sentences containing the searched word. It groups the sentences based on the
        child nodes of the token with the word being searched. Rules are applied to increase number of relations
        obtained.

        Args:
            argv: The command line arguments.
        """
        SentencesAccumulator.__init__(self, argv)
        ResultsGroupMatcher.__init__(self, argv)

        self.img_renderer = GroupImageRenderer(argv)

        self.argv = argv

    def group_accounting_add_by_tree(self, tree, token, sentence, img_path, extracted_relations, applied):
        """Groups the sentences based on the child nodes of the token with the word being searched.

        Args:
            tree: The NLTK tree with the node representation.
            token: The TreeNode SpaCy-like node.
            sentence: The raw sentence text.
            img_path: The path to the image related to this sentence.
            extracted_relations: The relations extracted from the sentence.
            applied: The rules applied to this sentence.
        """
        self.group_accounting_add(tree, token, sentence, img_path,
                                  tree, self.img_renderer, extracted_relations, applied)

    def filter(self, groups):
        """Given all groups and sentenes obtained, returns a sample of these sentences.

        Args:
            groups: The dictionary with the sentence groups.

        Returns:
            The dictionary with the sentence groups.
        """
        if self.argv.tetre_sampling is None:
            return groups

        sampling = float(self.argv.tetre_sampling)
        seed = int(self.argv.tetre_seed)

        simplified_groups = {}

        random.seed(seed)

        for key, group in self.groups.items():

            qty = int(percentage(sampling, len(group["sentences"])))

            if qty < 1:
                qty = 1

            simplified_groups[key] = {}
            for inner_key, inner_values in group.items():
                simplified_groups[key][inner_key] = inner_values

            simplified_groups[key].pop('sentences', None)
            simplified_groups[key]["sentences"] = []

            for i in range(0, qty):
                simplified_groups[key]["sentences"].append(
                    group["sentences"][i]
                )

        return simplified_groups

    def run(self):
        """Execution entry point.
        """
        rule_applier = Process()
        rule_applier_children = ProcessChildren()
        rule_extraction = ProcessExtraction()

        for token_original, sentence in get_tokens(self.argv):

            img_path = self.process_sentence(sentence)
            token = copy.deepcopy(token_original)
            tree = get_node_representation(self.argv.tetre_format, token)

            tree, applied_verb = rule_applier.apply_all(tree, token)

            tree_grouping = tree
            tree_subj_grouping = ""
            tree_obj_grouping = ""

            if self.argv.tetre_behaviour_root != "verb":
                tree_grouping = ""
                for child in token.children:
                    if self.argv.tetre_behaviour_root in child.dep_:
                        tree_grouping = get_node_representation(self.argv.tetre_format, child)
                    if "subj" in child.dep_:
                        tree_subj_grouping = get_node_representation(self.argv.tetre_format, child)
                    if "obj" in child.dep_:
                        tree_obj_grouping = get_node_representation(self.argv.tetre_format, child)

            tree_obj_grouping, tree_subj_grouping, applied_obj_subj = \
                rule_applier_children.apply_all(tree_obj_grouping,
                                                tree_subj_grouping,
                                                token)

            if "subj" in self.argv.tetre_behaviour_root:
                tree_grouping = tree_subj_grouping
            if "obj" in self.argv.tetre_behaviour_root:
                tree_grouping = tree_obj_grouping

            extracted_relations = rule_extraction.apply_all(tree, token, sentence)

            applied = applied_verb + applied_obj_subj

            self.group_accounting_add_by_tree(tree_grouping, token, sentence, img_path, extracted_relations, applied)

        self.set_groups(self.filter(self.get_groups()))

        output_generator = OutputGenerator(self.argv, self)

        if self.argv.tetre_output == "json":
            output_generator.graph_gen_json()
        elif self.argv.tetre_output == "html":
            output_generator.graph_gen_html()
