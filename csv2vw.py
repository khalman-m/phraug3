#!/usr/bin/env python
'Convert CSV file to Vowpal Wabbit format.'
'Allows mixing of categorical and numvoierical data'

import sys
import os
import csv
import argparse


class LineConverter(object):
    def __init__(self, filesize, col_names=None, convert_zeros=False, label_index=0, real_valued=None, ignore_columns=None):
        self.filesize = filesize
        self.bytes_counter = 0
        self.line_counter = 0
        self.convert_zeros = convert_zeros
        self.label_index = label_index
        self.col_names = col_names
        self.col_names.pop(label_index)

        if real_valued is None:
            self.real_valued = set()
        else:
            self.real_valued = set(map(int, real_valued.split(',')))

        if ignore_columns is None:
            self.ignore_columns = set()
        else:
            self.ignore_columns = set(map(int, ignore_columns.split(',')))

    @staticmethod
    def update_progress(progress, suffix=''):
        hashes_n = 20
        line = '#' * int(progress * hashes_n) + '_' * int((1 - progress) * hashes_n)
        sys.stdout.write('\r[{0}] {1}%'.format(line, int(100 * progress)) + suffix)
        sys.stdout.flush()

    @staticmethod
    def clean(item):
        return item.replace("|", "").replace(":", "")

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
        self.line_counter += 1
        if self.line_counter % 10000 == 0:
            self.update_progress(float(self.bytes_counter) / self.filesize)
        self.bytes_counter += 2  # 2 for \n and \r

        new_line = list()
        label = line.pop(self.label_index)
        new_line.append(self.handle_label(label))

        real_valued = dict()
        if self.col_names is None:
            self.col_names = ['c%03d' % (idx + 1) for idx in xrange(len(line))]
            self.col_names.pop(self.label_index)

        for i, item in enumerate(line):
            self.bytes_counter += len(item) + 1
            if i in self.ignore_columns:
                continue

            if i not in self.real_valued:
                new_item = "|{} {}".format(self.col_names[i], self.clean(item))
                new_line.append(new_item)
            else:
                try:
                    item_float = float(item)
                    if item_float == 0.0:
                        continue
                    real_valued[self.col_names[i]] = item_float
                except ValueError:
                    raise 'Error trying to convert %s to float (column %s, line %d)' % (item, self.col_names[i], self.line_counter)

        if len(real_valued) > 0:
            new_item = "|RealValued "
            for key in real_valued:
                new_item = new_item + '{}:{} '.format(key, real_valued[key])
            new_line.append(new_item)

        new_line = " ".join(new_line)
        new_line += "\n"
        return new_line

    def __del__(self):
        self.update_progress(1.0, '\n')


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

    parser.add_argument("-t", "--tsv", action="store_true", default=False,
                        help="for tsv files instead of csv - default false")

    args = vars(parser.parse_args())

    return args


def main():
    args = parse_args()

    if args.pop('tsv'):
        sep = '\t'
    else:
        sep = ','

    input_filename = args.pop('input_file')
    in_file = open(input_filename)
    filesize = os.path.getsize(input_filename)
    out_file = open(args.pop('output_file'), 'wb')

    reader = csv.reader(in_file, delimiter=sep)
    if args.pop('parse_header'):
        header = reader.next()
        col_names = [''.join(x.split(' ')) for x in header]
        filesize -= sum(len(x) for x in header)
    else:
        col_names = None

    constructor = LineConverter(col_names=col_names, filesize=filesize, **args)
    for line in reader:
        new_line = constructor.construct_line(line)
        out_file.write(new_line)

if __name__ == "__main__":
    main()
