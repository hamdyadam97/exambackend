"""
The platform's exam taxonomy, cleaned up from the old platform's export.

  Category (level 1) -> Sub Category (level 2) -> Sub Sub-Category (level 3)
  Section: shared by all exams (no category); only sections that have questions on the
           path the student picked appear in the exam builder.
  Topic:   belongs to one section; shown only as an optional filter inside its section.

Loaded with `python manage.py seed_taxonomy` (idempotent: creates what is missing, never deletes).
Cleanup applied to the export: duplicate spellings merged, truncated names completed,
exam years (2024/2026, Past Year Q) left for a question field instead of categories,
"Free Trial" and the 4th/5th/6th year groups dropped, placeholder topics (Test, General,
Miscellaneous, High Yield) dropped.
"""

MEDICINE_CORE = ['Internal Medicine', 'General Surgery', 'Pediatrics', 'Obstetrics and Gynecology', 'Basic Sciences']
HOSPITAL_EXAM = ['Internal Medicine', 'Pediatrics', 'Obstetrics and Gynecology', 'Basic Sciences']
DENTAL_SUBJECTS = [
    'Oral Medicine', 'Oral Surgery', 'Conservative Dentistry', 'Periodontology', 'Prosthodontics',
    'Orthodontics', 'Pedodontics', 'Dental Materials', 'Oral Histology',
]
NURSING_SUBJECTS = [
    'Medical-Surgical Nursing', 'Critical Care Nursing', 'Pediatric Nursing', 'Maternity Nursing',
    'Psychiatric Nursing', 'Nursing Management and Leadership',
]
PARTS = ['Part 1', 'Part 2']

RESIDENCY_SPECIALTIES = [
    'Internal Medicine', 'General Surgery', 'Pediatrics', 'Obstetrics and Gynecology', 'Ophthalmology',
    'ENT', 'Radiology', 'Nuclear Medicine', 'Forensic Medicine', 'Orthopedic Surgery', 'Dermatology',
    'Neurosurgery', 'Urology', 'Psychiatry', 'Anesthesia', 'Accident and Emergency Medicine',
    'Family Medicine', 'Pathology', 'Clinical Microbiology', 'Physical Medicine and Rehabilitation',
    'Dentistry',
]

# (level-1 name, [(level-2 name, [level-3 names])])
TREE = [
    ('JMC - الفحص الإجمالي', [
        ('Medicine - طب بشري (امتياز)', MEDICINE_CORE),
        ('Dentistry - طب أسنان', DENTAL_SUBJECTS),
    ]),
    ('Residency Entrance - امتحانات دخول الإقامة', [
        ('MOH - وزارة الصحة (التنافسي - دخول الإقامة)', HOSPITAL_EXAM),
        ('RMS - الخدمات الطبية الملكية', HOSPITAL_EXAM),
        ('JUH - مستشفى الجامعة الأردنية', HOSPITAL_EXAM),
        ('KAUH - مستشفى الملك المؤسس عبدالله', HOSPITAL_EXAM),
        ('KHCC - مركز الحسين للسرطان', HOSPITAL_EXAM),
        ('PH - مستشفى الأمير حمزة', HOSPITAL_EXAM),
        ('Dentistry - طب أسنان', DENTAL_SUBJECTS),
    ]),
    ('MOH Open Recruitment - وزارة الصحة (التنافسي - الإعلان المفتوح)', [
        ('Medicine - طب بشري', ['Internal Medicine', 'Obstetrics and Gynecology']),
    ]),
    ('Residency and Board Exams - البورد والإقامة', [
        (specialty, PARTS) for specialty in RESIDENCY_SPECIALTIES
    ]),
    ('SMLE - Prometric', [
        ('Medicine - طب بشري', ['Internal Medicine', 'General Surgery', 'Pediatrics', 'Obstetrics and Gynecology']),
        ('Nursing - تمريض', NURSING_SUBJECTS),
    ]),
    ('Nursing License - امتحان مزاولة المهنة للتمريض', [
        ('Nursing - تمريض', NURSING_SUBJECTS),
    ]),
    ('USMLE', [
        ('Highly Suggested Questions', ['Step 1', 'Step 2 CK']),
    ]),
    ('MRCP (UK)', [
        ('Part 1', ['Cardiology']),
    ]),
]

# Top-level categories already entered by hand under another spelling: the seed renames them
# (same row, so anything linked to them stays linked) instead of creating a duplicate.
ROOT_RENAMES = {
    'SMLE- prometric': 'SMLE - Prometric',
    'Residency and Board exams': 'Residency and Board Exams - البورد والإقامة',
    'Residency Entrance - Medicine': 'Residency Entrance - امتحانات دخول الإقامة',
    'USMLE highly suggested questions': 'USMLE',
    'MRCP': 'MRCP (UK)',
}

# Section -> its topics. Section names are unique; a topic name appears under one section only.
SECTIONS = {
    # Clinical systems
    'Respiratory System': [
        'Obstructive Lung Disease', 'Restrictive Lung Disease', 'Interstitial Lung Disease', 'Lung Neoplasms',
        'Pulmonary Vasculature Disease', 'Pulmonary Embolism', 'Pulmonary Edema', 'Pleural Diseases',
        'Pleural Effusion', 'Pneumothorax', 'Occupational Lung Diseases', 'Pneumonia',
        'Upper Respiratory Tract Infections', 'Lower Respiratory Tract Infections',
        'Neonatal Respiratory Conditions', 'Sleep Disorders',
    ],
    'Cardiovascular System': [
        'Ischemic Heart Disease', 'Acute Coronary Syndrome', 'Myocardial Infarction', 'Congestive Heart Failure',
        'Arrhythmias & ECG', 'Cardiomyopathies', 'Hypertrophic Cardiomyopathy', 'Pericardial Disease',
        'Valvular Heart Disease', 'Congenital Heart Disease', 'Arterial Diseases & Hypertension', 'Venous Diseases',
    ],
    'Gastrointestinal System': [
        'Esophageal Diseases', 'Stomach Diseases', 'Peptic Ulcer', 'Duodenal Ulcer', 'Gastric Cancer',
        'Small Intestine Diseases', 'Colon Diseases', 'Inflammatory Bowel Disease', 'Diverticulitis',
        'Diverticular Disease & Angiodysplasia', 'Rectal Disease', 'Perianal Diseases', 'Appendix Diseases',
        'Bowel Obstruction and Perforation', 'Functional Gastrointestinal Disorders', 'GI Bleeding',
        'Liver Diseases', 'Jaundice', 'Gallbladder Diseases', 'Pancreas Diseases', 'Salivary Gland Diseases',
    ],
    'Renal and Urinary System': [
        'Renal Failure', 'Proteinuria & Hematuria', 'Glomerular Disease', 'Nephrotic Syndrome',
        'Tubulointerstitial Disease', 'Renal Cystic Disease', 'Renal-Vascular Disease',
        'Renal Stones & Obstruction', 'Renal Neoplasms', 'Renal Infections', 'Bladder Diseases', 'Prostate Disease',
    ],
    'Fluids and Electrolytes': ['Electrolyte Disorders', 'Acid-Base Disorders', 'Fluid Replacement'],
    'Hematology': [
        'Anticoagulation', 'Platelets & Coagulopathies', 'Myeloproliferative Diseases', 'Plasma Cell Disorders',
        'Hodgkin Lymphoma', 'Non-Hodgkin Lymphoma', 'Spleen Diseases', 'Hyposplenism', 'Blood Transfusion',
        'Chemotherapy',
    ],
    'Endocrine': [
        'Thyroid Diseases', 'Hyperthyroidism', 'Graves Disease', 'Parathyroid Diseases', 'Pituitary Diseases',
        'Adrenal Diseases', 'Bone Disorders', 'Metabolic Disorders', 'Nutritional Disorders',
    ],
    'Rheumatology': [
        'Connective Tissue Diseases', 'Crystal-Induced Arthritis', 'Vasculitis', 'Osteoarthritis',
        'Rheumatoid Arthritis', 'Infectious Arthritis', 'Autoimmune Diseases', 'Granulomatous Diseases',
    ],
    'Immunology': ['Immunodeficiency Disorders', 'Allergic Reactions'],
    'Neurology': [
        'Movement Disorders', 'Altered Mental Status', 'Demyelinating Disease', 'Neuromuscular Disease',
        'Spinal Cord Diseases', 'Seizures', 'Meningitis & Encephalitis', 'Brain Tumor', 'Brain Hemorrhage',
        'Head Trauma', 'Basal Skull Fracture', 'Brain Death', 'Neural Tube Defects', 'Acute Flaccid Paralysis',
        'Infantile Hypotonia',
    ],
    'Infectious Diseases': [
        'Bacterial Infections', 'Viral Infections', 'Fungal Infections', 'Parasitic Infections',
        'Zoonotic Diseases', 'Sepsis', 'Septic Shock', 'Fever', 'HIV',
        'Sexually Transmitted Diseases (STD)', 'GI Infections', 'Genitourinary Infections',
        'Respiratory Infections', 'Ear Infections',
    ],
    'Reproductive System': [
        'Antenatal Care', 'Physiological Changes in Pregnancy', 'Pregnancy & Labor', 'Assisted Vaginal Delivery',
        'Ectopic Pregnancy', 'Antepartum Hemorrhage', 'Postpartum Hemorrhage',
        'Hypertensive Disorders of Pregnancy', 'Gestational Trophoblastic Neoplasia', 'Puerperium',
        'Multiple Pregnancy', 'Placental Disorders', 'Oligohydramnios and Polyhydramnios', 'Rh Incompatibility',
        'Drugs in Pregnancy', 'Pelvic Inflammatory Disease', 'Urinary Incontinence', 'Genital Prolapse',
        'Uterine Fibroid', 'Endometriosis', 'Infertility', 'Amenorrhea', 'Abnormal Uterine Bleeding',
        'Menorrhagia', 'Menopause', 'Polycystic Ovary Syndrome (PCOS)', 'Ovarian Disorders', 'Ovarian Cancer',
        'Endometrial Cancer', 'Cervical Cancer', 'Contraception', 'Testicular Diseases', 'Genital Disorders',
        'Embryology',
    ],
    'General Surgery': [
        'Pre- and Post-Operative Management', 'Abdominal Trauma', 'Hernia', 'Breast Diseases',
        'Wounds, Ulcers & Cysts', 'Bariatric Surgery', 'Vascular Surgery',
    ],
    'Thoracic Surgery': ['Chest Trauma'],
    'Pediatric Surgery': ['Intussusception', 'Congenital GI Defects'],
    'Plastic Surgery': [],
    'Pediatrics': ['Neonatology', 'Congenital Conditions'],
    'Growth and Development': ['Disorders of Growth', 'Developmental Assessment'],
    'Vaccination': ['Vaccines'],
    'Genetics': ['Genetic Disorders'],
    'Musculoskeletal System': ['Orthopedic Fractures', 'Orthopedic Tumors', 'Bone and Joint Disorders'],
    'Dermatology': ['Dermatitis', 'Skin Lesions', 'Skin Cancer'],
    'Psychiatry': ['Depression'],
    'Ophthalmology': ['Eye Infections'],
    'Pharmacology': ['Drug-Induced Diseases', 'Adverse Drug Reactions', 'Immunosuppressants (Cyclosporine)'],
    'Forensic Medicine and Toxicology': ['Poisoning'],
    'Emergency Medicine': [],
    'Family Medicine': [],
    'Public Health': [],
    'Radiology & Nuclear Medicine': [],
    'Biochemistry': [],
    'Internal Medicine': [],
    # Anesthesia (residency)
    'Anesthesia Physics and Equipment': [],
    'Clinical Anesthesia': ['IV Anesthesia', 'Obstetric Anesthesia', 'Liver Physiology in Anesthesia'],
    'Regional Anesthesia': ['Local Anesthesia'],
    'Cardiac Anesthesia': [],
    'Thoracic Anesthesia': [],
    'Pediatric Anesthesia': [],
    'Orthopedic and Trauma Anesthesia': [],
    # Dentistry
    'Dental Basic Sciences': [
        'Gross Anatomy', 'Head and Neck Anatomy', 'General Physiology', 'Oral Physiology', 'Cardiac Physiology',
        'Renal Physiology', 'Respiratory Physiology', 'Endocrine Physiology', 'Neurophysiology',
        'Dental Biochemistry', 'Vitamins', 'Microbiology', 'Dental Pharmacology',
    ],
    'Oral Biology and Pathology': [
        'Dental Anatomy and Oral Histology', 'Oral Embryology, Salivary Glands and TMJ', 'Oral Pathology',
        'Oral Neoplasms', 'Tissue Injury',
    ],
    'Clinical Dentistry': [
        'Dental Materials', 'Prosthodontics', 'Occlusion', 'Endodontic Surgery', 'Oral and Maxillofacial Surgery',
        'Dental Radiology', 'Infection Control', 'Periodontics',
    ],
    'Diagnosis and Non-Surgical Therapy': [],
    'Allergic, Metabolic and Infection-Related Emergencies': [],
    # Nursing
    'Arterial Blood Gases and Acid-Base Balance': [],
    'CPR and Chest Tube': [],
    'ECG Interpretation and Arrhythmia': [],
    'IV Fluids': [],
    'Surgical and Post-Operative Care': [],
    'Pediatric Congenital Anomalies': ['Cleft Lip and Palate', 'Spina Bifida', 'Hirschsprung Disease'],
    'Nervous System and Special Senses': [],
    'Multisystem': [],
    'Prenatal Care': [],
    'Physical Assessment': [],
    'Quality and Safety': [],
    'Nursing Management': [],
}
