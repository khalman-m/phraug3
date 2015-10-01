#!/usr/bin/env python
'Convert CSV file to Vowpal Wabbit format.'
'Allows mixing of categorical and numerical data'
# TODO add weights

import sys
import os
import csv
import itertools
import argparse

#TODO fix quadratics 0#1

QUADRATIC_SEP = ','

class AdvancedReader(object):

    def __init__(self, filename, tsv=None, progress=True):
        if tsv:
            sep = '\t'
        else:
            sep = ','

        in_file = open(filename)
        filesize = os.path.getsize(filename)
        self.bytes_counter = 0
        self.line_counter = 0

        self.reader = csv.reader(in_file, delimiter=sep)

        self.filesize = filesize
        self.progress = progress

    @staticmethod
    def update_progress(progress, suffix=''):
        hashes_n = 20
        line = '#' * int(progress * hashes_n) + '_' * int((1 - progress) * hashes_n)
        sys.stdout.write('\r[{0}] {1}%'.format(line, int(100 * progress)) + suffix)
        sys.stdout.flush()

    def next(self):
        self.line_counter += 1
        if self.progress and self.line_counter % 10000 == 0:
            self.update_progress(float(self.bytes_counter) / self.filesize)
        self.bytes_counter += 2  # 2 for \n and \r
        return_value = self.reader.next()
        self.bytes_counter += sum([len(x) for x in return_value])
        return return_value

    def __iter__(self):
        return self

    def __del__(self):
        self.update_progress(1.0, '\n')


class CSV2VWConverter(object):

    def __init__(self, input_file, output_file, convert_zeros=False, label_index=0,
                 real_valued=None, min_shows=1, ignore_columns=None, tsv=True, parse_header=False, skip_header=False,
                 quadratic=None):
        self.convert_zeros = convert_zeros
        self.label_index = label_index

        self.reader = AdvancedReader(input_file, tsv=tsv)

        if parse_header:
            header = self.reader.next()
            self.col_names = [''.join(x.split(' ')) for x in header]
        elif skip_header:
            header = self.reader.next()
            self.col_names = ['c%03d' % (idx + 1) for idx in xrange(len(header))]
        else:
            # Open new reader and read just one line to calculate number of features (namespaces)
            header_reader = AdvancedReader(input_file, tsv=tsv, progress=False)
            header = header_reader.next()
            self.col_names = ['c%03d' % (idx + 1) for idx in xrange(len(header))]

        self.col_names.pop(self.label_index)
        self.out_file = open(output_file, 'w')

        if real_valued is None:
            self.real_valued = set()
        else:
            self.real_valued = set(map(int, real_valued.split(',')))

        if ignore_columns is None:
            self.ignore_columns = set()
        else:
            self.ignore_columns = set(map(int, ignore_columns.split(',')))

        if quadratic is None:
            quadratic = []
        self.quadratic_indices = self.transform_quadratic_option(quadratic, self.col_names)
        self.col_names = self.add_quadratics(self.col_names, self.quadratic_indices)

        if min_shows > 1:
            self.filter_features = True
            min_shows_reader = AdvancedReader(input_file, tsv=tsv)
            self.features_to_use = self.calculate_features_to_use(min_shows, min_shows_reader)
        else:
            self.filter_features = False

    @staticmethod
    def transform_quadratic_option(quadratic, col_names):
        def get_col_ids_from_prefix(prefix, col_names):
            res = []
            for (i,x) in enumerate(col_names):
                if x.startswith(prefix):
                    res.append(i)
            return res
        result = []
        quadratic = [x.split(',') if ',' in x else x for x in quadratic]
        for ab in quadratic:
            for a_idx in get_col_ids_from_prefix(ab[0], col_names):
                for b_idx in get_col_ids_from_prefix(ab[1], col_names):
                    result.append((a_idx, b_idx))
        return result

    @staticmethod
    def add_quadratics(line, quadratic):
        for first, second in quadratic:
            new_item = []
            for a in line[first].split(' '):
                for b in line[second].split(' '):
                    new_item.append(a + '#' + b)
            line.append(' '.join(new_item))
        return line

    def calculate_features_to_use(self, min_shows, reader):
        print 'Calculating occurences of all features...'
        feature_count_dict = dict()
        for line in reader:
            line.pop(self.label_index)
            line = self.add_quadratics(line, self.quadratic_indices)

            for (i, item) in enumerate(line):
                if i in self.ignore_columns:
                    continue
                for feature in item.split(' '):
                    feature_with_name = self.col_names[i] + '|' + feature
                    if feature_with_name not in feature_count_dict:
                        feature_count_dict[feature_with_name] = 1
                    else:
                        feature_count_dict[feature_with_name] += 1

        print >>sys.stderr, len(feature_count_dict)
        features_to_use = set()
        for key in feature_count_dict:
            if feature_count_dict[key] >= min_shows:
                features_to_use.add(key)
        print >>sys.stderr, len(features_to_use)

        return features_to_use

    def clean(self, item, filter_features=False, col_name=None):
        item = item.replace("|", "").replace(":", "")  # clean trash
        if filter_features:
            item = ' '.join([x for x in item.split(' ') if (col_name + '|' + x) in self.features_to_use])
        return item

    def handle_label(self, label):
        try:
            label = float(label)

            if label == 0.0:
                if self.convert_zeros:
                    label = "-1"
                else:
                    label = "0"
            elif label == 1.0:
                label = '1'
        except:
            if label == '':
                print "WARNING: a label is ''"
            else:
                print "WARNING: a label is '{}', setting to ''".format(label)
                label = ''

        return label

    def construct_line(self, line):
        new_line = list()
        label = line.pop(self.label_index)
        line = self.add_quadratics(line, self.quadratic_indices)

        new_line.append(self.handle_label(label))

        real_valued = dict()

        cur_features = dict(keys=self.col_names)
        for i, item in enumerate(line):
            if i in self.ignore_columns:
                continue
            if i not in self.real_valued:
                item = self.clean(item, filter_features=self.filter_features, col_name=self.col_names[i])
                cur_features[self.col_names[i]] = item
                new_item = "|{} {}".format(self.col_names[i], item)
                new_line.append(new_item)
            else:
                try:
                    item_float = float(item)
                    if item_float == 0.0:
                        pcontinue
                    real_valued[self.col_names[i]] = item_float
                except ValueError:
                    raise 'Error trying to convert %s to float (column %s, line %d)' % (
                        item, self.col_names[i], self.line_counter)

        if len(real_valued) > 0:
            new_item = "|RealValued "
            for key in real_valued:
                new_item = new_item + '{}:{} '.format(key, real_valued[key])
            new_line.append(new_item)

        new_line = " ".join(new_line)
        new_line += "\n"
        return new_line

    def convert(self):
        print 'Converting...'
        for line in self.reader:
            new_line = self.construct_line(line)
            self.out_file.write(new_line)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Convert CSV/TSV file to Vowpal Wabbit format.')
    parser.add_argument("input_file", help="path to csv input file")
    parser.add_argument("output_file", help="path to output file")

    parser.add_argument(
        "-p",
        "--parse_header",
        action="store_true",
        help="Use this option if there is a header in the file. Parse header for namespace names")

    parser.add_argument(
        "-s",
        "--skip_header",
        action="store_true",
        help="Use this option if there is a header in the file and you just want to skip it (use made up names instead)")

    parser.add_argument(
        "-l",
        "--label_index",
        type=int,
        default=0,
        help="index of label column (default 0, use -1 if there are no labels)")

    parser.add_argument(
        "-z",
        "--convert_zeros",
        action='store_true',
        default=False,
        help="convert labels for binary classification from 0 to -1")

    parser.add_argument(
        "-i",
        "--ignore_columns",
        help="zero-based index(es) of columns to ignore, for example 0 or 3 or 3,4,5 (no spaces in between)")

    parser.add_argument(
        "-r",
        "--real_valued",
        help="zero-based index(es) of columns to treat as real-valued.")

    parser.add_argument(
        "-q",
        "--quadratic",
        action='append',
        help='''
            manually creates namespace for products of features. Syntax is the same as vw syntax.
            But be careful, works only for tables with headers. (-p option)
            ''')

    parser.add_argument(
        "-m",
        "--min_shows",
        type=int,
        default=1,
        help='''
            min_shows filtering for regularization. -m <ms> leaves only features that occurred >= <ms> times.
            <ms>=1 is equivalent to no min shows at all.
            Be careful, when you convert data using min_shows filtering, script stores all occurences in the memory.
            RAM consumption may be as big as the volume of your input data.
            ''')

    parser.add_argument("-t", "--tsv", action="store_true", default=False,
                        help="for tsv files instead of csv - default false")

    args = vars(parser.parse_args())

    return args


def main():
    args = parse_args()

    converter = CSV2VWConverter(**args)
    converter.convert()

if __name__ == "__main__":
    main()
