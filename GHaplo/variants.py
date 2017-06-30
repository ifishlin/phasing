__author__ = 'ifish'

import logging
import sys
from collections import OrderedDict

import pysam
import numpy as np
from scipy.sparse import csr_matrix, lil_matrix

class InputVcfReader(object):
    """
    """
    encoding_table = {'A':1, 'T':2, 'C':3, 'G':4, 1:'A', 2:'T', 3:'C', 4:'G', 0:' ', ' ':0, 6:'-', '-':6}


    def __init__(self, haplo_file, bam_file, min_base_quality, min_read_quality, cc_input=None, indels=False, trust=True):
        self.haplo_file = haplo_file
        self.bam_file = bam_file
        self.indels = indels
        self.min_base_quality = min_base_quality
        self.min_read_quality = min_read_quality
        self.trust = trust
        self.cc_input = cc_input
        self.reads_proxy = None
        #self.reads_proxy = pysam.AlignmentFile(self.bam_file, "rb")    
        self.encoding_table = {'A':1, 'T':2, 'C':3, 'G':4, 1:'A', 2:'T', 3:'C', 4:'G', 0:' ', ' ':0, 6:'-', '-':6}

        #self.reads_proxy = None
        self.logging = logging

    def reset(self, haplo_file, bam_file, min_base_quality, min_read_quality, cc_input=None, indels=False, trust=True):
        self.haplo_file = haplo_file
        self.bam_file = bam_file
        self.indels = indels
        self.min_base_quality = min_base_quality
        self.min_read_quality = min_read_quality
        self.trust = trust
        self.cc_input = cc_input
        #self.reads_proxy = pysam.AlignmentFile(self.bam_file, "rb")    
        self.encoding_table = {'A':1, 'T':2, 'C':3, 'G':4, 1:'A', 2:'T', 3:'C', 4:'G', 0:' ', ' ':0, 6:'-', '-':6}

        #self.reads_proxy = None
        self.logging = logging



    def get_readmtx(self, timer):
        """
        Args:

        Return:
            read_matrix
            read_matrix_xaxis
            read_matrix_yaxis
            read_matrix_ref
            encoding_table
        
            read_matrix
            phase_fragments_dict
            phase_fragments_range_list
            phase_variants_location_list
            HaploReader.encoding_table
            phase_variants_called_list

        Comment:
            phase_input = [[chrom_id, variant_loc, extesion_length, variant_type, ref_major, called_h1, called_h2], ... ]

            phase_fragments_dict = {read1_id:[(chrom, v1_loc, allele, type), (chrom, v2_loc, allele, type), ... ], read2_id: ... }
            phase_fragments_range_list = [[read1_id, min_loc, max_loc], [read2_id, min_loc, max_loc], ... ]
            phase_variants_location_list = [v1_loc, v2_loc, v3_loc ... ]
            phase_variants_called_list = [(ref_major, called_h1, called_h2), (ref_major, called_h1, called_h2), ... ]
        """

        #logging.info("start _load_haplo")
        phase_input = self.cc_input

        timer.start('readmtx_init')
        phase_variants_location_list = list(map(lambda x:x[1], phase_input))
        phase_variants_called_list = list(map(lambda x:(x[4],x[5],x[6]), phase_input))
        phase_fragments_dict = OrderedDict()
        timer.stop('readmtx_init')
        #logging.info("start _read_variance")

        # Open Pysam 
        if self.reads_proxy == None:
            self.reads_proxy = pysam.AlignmentFile(self.bam_file, "rb")

        #timer.start('read_variance')
        # Read from Pysam
        for vd in phase_input:
            self._read_variance(vd[0], vd[1], vd[2], vd[3], phase_fragments_dict, (vd[5], vd[6]), self.trust, timer)
        #timer.stop('read_variance')

        # Close Pysam
        #self.reads_proxy.close()

        timer.start('clear_matrix')
        self._clear_matrix(phase_fragments_dict)
        timer.stop('clear_matrix')

        #logging.info("start _read_matrix")
        #read_matrix = np.zeros(shape=(len(phase_fragments_dict), len(phase_variants_location_list)), dtype='int')
        read_matrix = lil_matrix((len(phase_fragments_dict), len(phase_variants_location_list)), dtype=np.int8)

        #logging.info("start _produce_var_matrix")
        timer.start('produce_var_matrix')
        phase_fragments_range_list = self._produce_var_matrix(read_matrix, phase_fragments_dict, phase_variants_location_list, InputVcfReader.encoding_table)
        timer.stop('produce_var_matrix')

        #del phase_input 
        return read_matrix, phase_fragments_dict, phase_fragments_range_list, phase_variants_location_list, InputVcfReader.encoding_table, phase_variants_called_list


    def _clear_matrix(self, phase_fragments_dict):
        """
        Remove unqualified read from v_desc_dict. (1). remove reads that cover less than two variants.


        """
        noninfo = []
        for x,y in phase_fragments_dict.items():
            a = [z[2] for z in y]
            if '-' in a:
                a.remove('-')
            if(len(a) < 2):
                noninfo.append(x)
        
        for x in noninfo:
            del phase_fragments_dict[x]

    def _read_variance(self, chrom, loci, extend_len, var_type, phase_fragments_dict, ref, trust, timer):
        """
        Read raw NGS data of each variants from sam file.

        """

        removed_set = set()
        # (loci - 1) in array = loci in seqs
        timer.start('fetch')
        for read in self.reads_proxy.fetch(chrom, loci - 1, loci):
            timer.stop('fetch')
            #read quality filter

            if(read.mapping_quality < self.min_read_quality):
                continue

            '''
            #treat as single-end
            id_suffix = ':NP'

            if read.is_proper_pair and read.is_read1:
                id_suffix = ":R1"
            elif read.is_proper_pair and read.is_read2:
                id_suffix = ":R2"

            #treat as paired-end
            id_suffix = ''

            #read_id
            read_id = read.query_name + id_suffix
            '''

            if not read.is_proper_pair:
                continue

            if read.is_read1 == True:
                read_id = read.query_name + "_" + str(read.next_reference_start)
            else:
                read_id = read.query_name + "_" + str(read.reference_start)


            timer.start('aligned_pairs')

            allele = ''
            read_indel_type = 'S'
            aligned_pairs = read.get_aligned_pairs()
            aligned = [i[1] for i in aligned_pairs]
            try:

                idx = aligned.index(loci - 1)
                observed = read.seq[aligned_pairs[idx][0]]

                if(aligned_pairs[idx][0] == None):
                    allele = '-'
                elif(observed not in ref and trust == True):
                    allele = '-'
                else:
                    allele = observed

            except (ValueError, TypeError) as error:
                allele = '-'
                pass
            '''

            for aligned in aligned_pairs:
                if aligned[1] == loci - 1:
                    if(aligned[0] == None):
                        allele = '-'
                        break

                    allele = read.seq[aligned[0]]

                    if(allele not in ref and trust == True):
                        allele = '-'
                        break
            '''

            timer.stop('aligned_pairs')

            timer.start('phase_fragments_dict')
            if(read_id in phase_fragments_dict):
                #overlapping paired-end, but different in target allele
                overlapped = False
                for i in phase_fragments_dict[read_id]:
                    if i[1] == loci:
                        overlapped = True
                        if(i[2] != allele):
                            removed_set.add(read_id)
                        break

                if not overlapped:
                    phase_fragments_dict[read_id].append((chrom, loci, allele, read_indel_type))
            else:
                phase_fragments_dict[read_id] = [(chrom, loci, allele, read_indel_type)]
            timer.stop('phase_fragments_dict')
            timer.start('fetch')
        timer.stop('fetch')
        #remove unqualified reads
        timer.start('removed_set')
        for i in removed_set:
            del phase_fragments_dict[i]
        timer.stop('removed_set')
 
        return

    def _produce_var_matrix(self, read_matrix, phase_fragments_dict, phase_variants_location_list, encoding_table):
        """

        """
        #vertical
        phase_fragments_range_list = []
        v_idx = 0
        code_num = len(encoding_table)/2

        loc_idx_dict = {y:x for x,y in dict(enumerate(phase_variants_location_list, 0)).items()}

        for read_id, variances in phase_fragments_dict.items():
            min_loc = loc_idx_dict[variances[0][1]]
            max_loc = loc_idx_dict[variances[-1][1]]

            phase_fragments_range_list.append((read_id, min_loc, max_loc))
            for chrom, loci, allele, atype in variances:
                h_idx = loc_idx_dict[loci]
                if(allele in encoding_table):
                    code = encoding_table[allele]
                else:
                    code = code_num
                    code_num += 1
                    encoding_table[allele] = code
                    encoding_table[code] = allele
                read_matrix[v_idx, h_idx] = code
            v_idx += 1

        return phase_fragments_range_list


