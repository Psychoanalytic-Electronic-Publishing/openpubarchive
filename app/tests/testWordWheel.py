#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import requests

from unitTestConfig import base_plus_endpoint_encoded, headers
import opasAPISupportLib
import timeit

class TestWordWheel(unittest.TestCase):

    def test_0a_get_term_index(self):
        resp = opasAPISupportLib.get_term_index("psycho",
                                                term_field="text",
                                                core="docs", 
                                                order="index")
        print (resp.termIndex.responseInfo.count)
        assert(resp.termIndex.responseInfo.count >= 10)

    def test_0a_get_term_index_timing(self):
        test = 'opasAPISupportLib.get_term_index("psycho",term_field="text",core="docs",order="index")'

        timing = timeit.timeit(test, setup="import opasAPISupportLib", number=1)
        print (f"timing: {timing}")
        assert(timing < .4)

    def test_1a_get_term_index(self):
        resp = opasAPISupportLib.get_term_index("tuck",
                                                term_field="art_author_id",
                                                core="authors", 
                                                order="index")
        print (resp.termIndex.responseInfo.count)
        assert(resp.termIndex.responseInfo.count >= 7)

    def test_2a_get_term_index_api(self):
        full_URL = base_plus_endpoint_encoded('/v2/Database/WordWheel/?word=measuring&core=docs')
        response = requests.get(full_URL, headers=headers)
        assert(response.ok == True)
        r = response.json()
        print (r)
        response_info = r["termIndex"]["responseInfo"]
        response_set = r["termIndex"]["responseSet"] 
        assert(response_set[0]["termCount"] >= 3)
        print (response_set)
        
    #def test_1a_termlist(self):
        #tests = ["jealous", "incest", "moth", "dog", "cat"]
        #term_list = opasAPISupportLib.get_term_count_list(tests)
        #assert(len(term_list) > 0)
        #for k,c in term_list.items():
            #print (f"{k} - {c}")
        
    #def test_1b_termlist(self):
        #tests = ["jea?ous?", "inc*", "m?th*"]
        #term_list = opasAPISupportLib.get_term_count_list(tests)
        #assert(len(term_list) > 0)
        #for k,c in term_list.items():
            #print (f"{k} - {c}")

    #def test_2a_termcsvlist(self):
        #terms = "freud, heart, mother, moth"
        #term_list = opasAPISupportLib.get_term_count_list(terms)
        #assert(len(term_list) > 0)
        #for k,c in term_list.items():
            #print (f"{k} - {c}")



if __name__ == '__main__':
    unittest.main()
