# S127 host counter attribution (read-only)

`AUTHORITY=0`; run `gt06-s127-post-failure-full-01`; formal acceptance and dataset eligibility are false.

Baseline batch 4: host handles 209, host RSS 52322304, editor handles 559, objects 71130, resources 6.

Observed rows:
- batch 0: host handles 209, host RSS 50221056, editor handles 565, editor objects/resources 71130/6, status gap 552.531 ms
- batch 1: host handles 209, host RSS 50733056, editor handles 559, editor objects/resources 71130/6, status gap 721.041 ms
- batch 2: host handles 209, host RSS 51466240, editor handles 559, editor objects/resources 71130/6, status gap 806.710 ms
- batch 3: host handles 209, host RSS 50917376, editor handles 555, editor objects/resources 71130/6, status gap 706.181 ms
- batch 4: host handles 209, host RSS 52322304, editor handles 559, editor objects/resources 71130/6, status gap 544.755 ms
- batch 5: host handles 209, host RSS 53452800, editor handles 555, editor objects/resources 71130/6, status gap 579.695 ms
- batch 6: host handles 209, host RSS 53673984, editor handles 555, editor objects/resources 71130/6, status gap 584.973 ms
- batch 7: host handles 209, host RSS 53690368, editor handles 555, editor objects/resources 71130/6, status gap 763.959 ms
- batch 8: host handles 209, host RSS 53133312, editor handles 555, editor objects/resources 71130/6, status gap 665.146 ms
- batch 9: host handles 209, host RSS 53526528, editor handles 555, editor objects/resources 71130/6, status gap 700.904 ms
- batch 10: host handles 209, host RSS 53428224, editor handles 557, editor objects/resources 71130/6, status gap 746.829 ms
- batch 11: host handles 209, host RSS 55238656, editor handles 557, editor objects/resources 71130/6, status gap 846.377 ms
- batch 12: host handles 209, host RSS 54460416, editor handles 557, editor objects/resources 71130/6, status gap 1058.006 ms
- batch 13: host handles 209, host RSS 55308288, editor handles 557, editor objects/resources 71130/6, status gap 550.904 ms
- batch 14: host handles 209, host RSS 55304192, editor handles 557, editor objects/resources 71130/6, status gap 776.054 ms
- batch 15: host handles 209, host RSS 56418304, editor handles 555, editor objects/resources 71130/6, status gap 1198.154 ms
- batch 16: host handles 209, host RSS 56229888, editor handles 557, editor objects/resources 71130/6, status gap 537.530 ms
- batch 17: host handles 209, host RSS 56586240, editor handles 557, editor objects/resources 71130/6, status gap 931.178 ms
- batch 18: host handles 210, host RSS 56786944, editor handles 555, editor objects/resources 71130/6, status gap 543.228 ms

At batch18 the host handle counter is 210 (+1), so the original gate rejects. The editor handle counter is 555 (−4) and editor objects/resources remain 71130/6. This is a counter boundary only; numeric counts do not establish persistent kernel identity or root cause. The report is derived from preserved raw sample files and is excluded from F13/F14.
