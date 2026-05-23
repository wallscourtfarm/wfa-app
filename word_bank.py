"""
WFA Key Spelling Word Bank
CEW / HFW / Key Spelling words from Reception through Year 6.
Each entry: (word, year, ks, phase, label)
  year:  'R', '1', '2', '3', '4', '5', '6'
  ks:    'EYFS', 'KS1', 'KS2'
  phase: '', 'LKS2', 'UKS2'
  label: 'CEW', 'HFW', 'Key Spelling'

Children work through this list in order. word_pos is their current index.
Mastered words are stored separately. Active list = next 5 unmastered from pos.
"""

WORD_BANK = [
    # ── Reception ──────────────────────────────────────────────────────────
    ('I','R','EYFS','','CEW'),('no','R','EYFS','','CEW'),('go','R','EYFS','','CEW'),
    ('to','R','EYFS','','CEW'),('the','R','EYFS','','CEW'),('is','R','EYFS','','CEW'),
    ('his','R','EYFS','','CEW'),('of','R','EYFS','','CEW'),('he','R','EYFS','','CEW'),
    ('she','R','EYFS','','CEW'),('we','R','EYFS','','CEW'),('me','R','EYFS','','CEW'),
    ('be','R','EYFS','','CEW'),('you','R','EYFS','','CEW'),('are','R','EYFS','','CEW'),
    ('her','R','EYFS','','CEW'),('was','R','EYFS','','CEW'),('all','R','EYFS','','CEW'),
    ('they','R','EYFS','','CEW'),('my','R','EYFS','','CEW'),('by','R','EYFS','','CEW'),
    ('into','1','KS1','','CEW'),
    # ── Year 1 CEW ─────────────────────────────────────────────────────────
    ('ask','1','KS1','','CEW'),('asked','1','KS1','','CEW'),('called','1','KS1','','CEW'),
    ('come','1','KS1','','CEW'),('could','1','KS1','','CEW'),('do','1','KS1','','CEW'),
    ('friend','1','KS1','','CEW'),('full','1','KS1','','CEW'),('has','1','KS1','','CEW'),
    ('have','1','KS1','','CEW'),('here','1','KS1','','CEW'),('house','1','KS1','','CEW'),
    ('like','1','KS1','','CEW'),('little','1','KS1','','CEW'),('looked','1','KS1','','CEW'),
    ('love','1','KS1','','CEW'),('Mr','1','KS1','','CEW'),('Mrs','1','KS1','','CEW'),
    ('oh','1','KS1','','CEW'),('once','1','KS1','','CEW'),('one','1','KS1','','CEW'),
    ('our','1','KS1','','CEW'),('out','1','KS1','','CEW'),('people','1','KS1','','CEW'),
    ('pull','1','KS1','','CEW'),('push','1','KS1','','CEW'),('put','1','KS1','','CEW'),
    ('said','1','KS1','','CEW'),('says','1','KS1','','CEW'),('school','1','KS1','','CEW'),
    ('so','1','KS1','','CEW'),('some','1','KS1','','CEW'),('their','1','KS1','','CEW'),
    ('there','1','KS1','','CEW'),('today','1','KS1','','CEW'),('were','1','KS1','','CEW'),
    ('what','1','KS1','','CEW'),('when','1','KS1','','CEW'),('where','1','KS1','','CEW'),
    ('your','1','KS1','','CEW'),
    # ── Year 1 HFW ─────────────────────────────────────────────────────────
    ('back','1','KS1','','HFW'),('came','1','KS1','','HFW'),('down','1','KS1','','HFW'),
    ('from','1','KS1','','HFW'),('help','1','KS1','','HFW'),('just','1','KS1','','HFW'),
    ('that','1','KS1','','HFW'),('them','1','KS1','','HFW'),('then','1','KS1','','HFW'),
    ('this','1','KS1','','HFW'),('time','1','KS1','','HFW'),('very','1','KS1','','HFW'),
    ('went','1','KS1','','HFW'),('will','1','KS1','','HFW'),('with','1','KS1','','HFW'),
    ('about','1','KS1','','HFW'),
    # ── Year 2 CEW ─────────────────────────────────────────────────────────
    ('bath','2','KS1','','CEW'),('both','2','KS1','','CEW'),('cold','2','KS1','','CEW'),
    ('door','2','KS1','','CEW'),('even','2','KS1','','CEW'),('fast','2','KS1','','CEW'),
    ('find','2','KS1','','CEW'),('gold','2','KS1','','CEW'),('kind','2','KS1','','CEW'),
    ('last','2','KS1','','CEW'),('many','2','KS1','','CEW'),('mind','2','KS1','','CEW'),
    ('most','2','KS1','','CEW'),('move','2','KS1','','CEW'),('only','2','KS1','','CEW'),
    ('pass','2','KS1','','CEW'),('past','2','KS1','','CEW'),('path','2','KS1','','CEW'),
    ('poor','2','KS1','','CEW'),('sure','2','KS1','','CEW'),('told','2','KS1','','CEW'),
    ('wild','2','KS1','','CEW'),("it's",'2','KS1','','HFW'),('after','2','KS1','','CEW'),
    ('again','2','KS1','','CEW'),('break','2','KS1','','CEW'),('child','2','KS1','','CEW'),
    ('class','2','KS1','','CEW'),('climb','2','KS1','','CEW'),('every','2','KS1','','CEW'),
    ('floor','2','KS1','','CEW'),('grass','2','KS1','','CEW'),('great','2','KS1','','CEW'),
    ('money','2','KS1','','CEW'),('plant','2','KS1','','CEW'),('prove','2','KS1','','CEW'),
    ('steak','2','KS1','','CEW'),('sugar','2','KS1','','CEW'),('whole','2','KS1','','CEW'),
    ('would','2','KS1','','CEW'),("don't",'2','KS1','','HFW'),('water','2','KS1','','HFW'),
    ('behind','2','KS1','','CEW'),('father','2','KS1','','CEW'),('pretty','2','KS1','','CEW'),
    ('should','2','KS1','','CEW'),('because','2','KS1','','CEW'),('clothes','2','KS1','','CEW'),
    ('parents','2','KS1','','CEW'),('children','2','KS1','','CEW'),
    ('beautiful','2','KS1','','CEW'),('Christmas','2','KS1','','CEW'),
    ('everybody','2','KS1','','CEW'),
    # ── Year 3 Key Spellings ───────────────────────────────────────────────
    ('eight','3','KS2','LKS2','Key Spelling'),('earth','3','KS2','LKS2','Key Spelling'),
    ('eighth','3','KS2','LKS2','Key Spelling'),('forwards','3','KS2','LKS2','Key Spelling'),
    ('height','3','KS2','LKS2','Key Spelling'),('weight','3','KS2','LKS2','Key Spelling'),
    ('length','3','KS2','LKS2','Key Spelling'),('learn','3','KS2','LKS2','Key Spelling'),
    ('describe','3','KS2','LKS2','Key Spelling'),('address','3','KS2','LKS2','Key Spelling'),
    ('fruit','3','KS2','LKS2','Key Spelling'),('question','3','KS2','LKS2','Key Spelling'),
    ('group','3','KS2','LKS2','Key Spelling'),('reign','3','KS2','LKS2','Key Spelling'),
    ('famous','3','KS2','LKS2','Key Spelling'),('history','3','KS2','LKS2','Key Spelling'),
    ('century','3','KS2','LKS2','Key Spelling'),('heart','3','KS2','LKS2','Key Spelling'),
    ('heard','3','KS2','LKS2','Key Spelling'),('strange','3','KS2','LKS2','Key Spelling'),
    ('build','3','KS2','LKS2','Key Spelling'),('often','3','KS2','LKS2','Key Spelling'),
    ('arrive','3','KS2','LKS2','Key Spelling'),('straight','3','KS2','LKS2','Key Spelling'),
    ('quarter','3','KS2','LKS2','Key Spelling'),('special','3','KS2','LKS2','Key Spelling'),
    ('decide','3','KS2','LKS2','Key Spelling'),('appear','3','KS2','LKS2','Key Spelling'),
    ('material','3','KS2','LKS2','Key Spelling'),('different','3','KS2','LKS2','Key Spelling'),
    ('island','3','KS2','LKS2','Key Spelling'),('popular','3','KS2','LKS2','Key Spelling'),
    ('surprise','3','KS2','LKS2','Key Spelling'),('therefore','3','KS2','LKS2','Key Spelling'),
    ('early','3','KS2','LKS2','Key Spelling'),('natural','3','KS2','LKS2','Key Spelling'),
    ('difficult','3','KS2','LKS2','Key Spelling'),('guard','3','KS2','LKS2','Key Spelling'),
    ('busy','3','KS2','LKS2','Key Spelling'),('answer','3','KS2','LKS2','Key Spelling'),
    ('remember','3','KS2','LKS2','Key Spelling'),('consider','3','KS2','LKS2','Key Spelling'),
    ('disappear','3','KS2','LKS2','Key Spelling'),('mention','3','KS2','LKS2','Key Spelling'),
    ('notice','3','KS2','LKS2','Key Spelling'),('peculiar','3','KS2','LKS2','Key Spelling'),
    ('calendar','3','KS2','LKS2','Key Spelling'),('potatoes','3','KS2','LKS2','Key Spelling'),
    ('stomach','3','KS2','LKS2','Key Spelling'),('system','3','KS2','LKS2','Key Spelling'),
    ('opposite','3','KS2','LKS2','Key Spelling'),('sentence','3','KS2','LKS2','Key Spelling'),
    ('particular','3','KS2','LKS2','Key Spelling'),('ordinary','3','KS2','LKS2','Key Spelling'),
    # ── Year 4 Key Spellings ───────────────────────────────────────────────
    ('minute','4','KS2','LKS2','Key Spelling'),('circle','4','KS2','LKS2','Key Spelling'),
    ('February','4','KS2','LKS2','Key Spelling'),('believe','4','KS2','LKS2','Key Spelling'),
    ('woman','4','KS2','LKS2','Key Spelling'),('women','4','KS2','LKS2','Key Spelling'),
    ('guide','4','KS2','LKS2','Key Spelling'),('favourite','4','KS2','LKS2','Key Spelling'),
    ('breath','4','KS2','LKS2','Key Spelling'),('breathe','4','KS2','LKS2','Key Spelling'),
    ('although','4','KS2','LKS2','Key Spelling'),('experiment','4','KS2','LKS2','Key Spelling'),
    ('thought','4','KS2','LKS2','Key Spelling'),('separate','4','KS2','LKS2','Key Spelling'),
    ('probably','4','KS2','LKS2','Key Spelling'),('strength','4','KS2','LKS2','Key Spelling'),
    ('through','4','KS2','LKS2','Key Spelling'),('bicycle','4','KS2','LKS2','Key Spelling'),
    ('purpose','4','KS2','LKS2','Key Spelling'),('recent','4','KS2','LKS2','Key Spelling'),
    ('actually','4','KS2','LKS2','Key Spelling'),('actual','4','KS2','LKS2','Key Spelling'),
    ('increase','4','KS2','LKS2','Key Spelling'),('important','4','KS2','LKS2','Key Spelling'),
    ('accident','4','KS2','LKS2','Key Spelling'),('accidentally','4','KS2','LKS2','Key Spelling'),
    ('centre','4','KS2','LKS2','Key Spelling'),('promise','4','KS2','LKS2','Key Spelling'),
    ('exercise','4','KS2','LKS2','Key Spelling'),('muscle','4','KS2','LKS2','Key Spelling'),
    ('shoulder','4','KS2','LKS2','Key Spelling'),('medicine','4','KS2','LKS2','Key Spelling'),
    ('knowledge','4','KS2','LKS2','Key Spelling'),('regular','4','KS2','LKS2','Key Spelling'),
    ('enough','4','KS2','LKS2','Key Spelling'),('naughty','4','KS2','LKS2','Key Spelling'),
    ('possible','4','KS2','LKS2','Key Spelling'),('interest','4','KS2','LKS2','Key Spelling'),
    ('pressure','4','KS2','LKS2','Key Spelling'),('certain','4','KS2','LKS2','Key Spelling'),
    ('though','4','KS2','LKS2','Key Spelling'),('suppose','4','KS2','LKS2','Key Spelling'),
    ('perhaps','4','KS2','LKS2','Key Spelling'),('caught','4','KS2','LKS2','Key Spelling'),
    ('occasion','4','KS2','LKS2','Key Spelling'),('occasionally','4','KS2','LKS2','Key Spelling'),
    ('ancient','4','KS2','LKS2','Key Spelling'),('continue','4','KS2','LKS2','Key Spelling'),
    ('complete','4','KS2','LKS2','Key Spelling'),('excellent','4','KS2','LKS2','Key Spelling'),
    ('experience','4','KS2','LKS2','Key Spelling'),('extreme','4','KS2','LKS2','Key Spelling'),
    ('position','4','KS2','LKS2','Key Spelling'),('possess','4','KS2','LKS2','Key Spelling'),
    # ── Year 5 Key Spellings ───────────────────────────────────────────────
    ('various','5','KS2','UKS2','Key Spelling'),('forty','5','KS2','UKS2','Key Spelling'),
    ('sincerely','5','KS2','UKS2','Key Spelling'),('sincere','5','KS2','UKS2','Key Spelling'),
    ('disaster','5','KS2','UKS2','Key Spelling'),('disastrous','5','KS2','UKS2','Key Spelling'),
    ('temperature','5','KS2','UKS2','Key Spelling'),('library','5','KS2','UKS2','Key Spelling'),
    ('business','5','KS2','UKS2','Key Spelling'),('curiosity','5','KS2','UKS2','Key Spelling'),
    ('programme','5','KS2','UKS2','Key Spelling'),('identity','5','KS2','UKS2','Key Spelling'),
    ('desperate','5','KS2','UKS2','Key Spelling'),('persuade','5','KS2','UKS2','Key Spelling'),
    ('suggest','5','KS2','UKS2','Key Spelling'),('develop','5','KS2','UKS2','Key Spelling'),
    ('bargain','5','KS2','UKS2','Key Spelling'),('interrupt','5','KS2','UKS2','Key Spelling'),
    ('interfere','5','KS2','UKS2','Key Spelling'),('exaggerate','5','KS2','UKS2','Key Spelling'),
    ('individual','5','KS2','UKS2','Key Spelling'),('relevant','5','KS2','UKS2','Key Spelling'),
    ('explanation','5','KS2','UKS2','Key Spelling'),('according','5','KS2','UKS2','Key Spelling'),
    ('vehicle','5','KS2','UKS2','Key Spelling'),('leisure','5','KS2','UKS2','Key Spelling'),
    ('familiar','5','KS2','UKS2','Key Spelling'),('attached','5','KS2','UKS2','Key Spelling'),
    ('category','5','KS2','UKS2','Key Spelling'),('existence','5','KS2','UKS2','Key Spelling'),
    ('variety','5','KS2','UKS2','Key Spelling'),('harass','5','KS2','UKS2','Key Spelling'),
    ('imagine','5','KS2','UKS2','Key Spelling'),('signature','5','KS2','UKS2','Key Spelling'),
    ('occur','5','KS2','UKS2','Key Spelling'),('occupy','5','KS2','UKS2','Key Spelling'),
    ('awkward','5','KS2','UKS2','Key Spelling'),('convenience','5','KS2','UKS2','Key Spelling'),
    ('possession','5','KS2','UKS2','Key Spelling'),('government','5','KS2','UKS2','Key Spelling'),
    ('profession','5','KS2','UKS2','Key Spelling'),('controversy','5','KS2','UKS2','Key Spelling'),
    ('correspond','5','KS2','UKS2','Key Spelling'),('conscious','5','KS2','UKS2','Key Spelling'),
    ('conscience','5','KS2','UKS2','Key Spelling'),('grammar','5','KS2','UKS2','Key Spelling'),
    ('accompany','5','KS2','UKS2','Key Spelling'),('physical','5','KS2','UKS2','Key Spelling'),
    ('neighbour','5','KS2','UKS2','Key Spelling'),('sacrifice','5','KS2','UKS2','Key Spelling'),
    ('pronunciation','5','KS2','UKS2','Key Spelling'),
    # ── Year 6 Key Spellings ───────────────────────────────────────────────
    ('immediate','6','KS2','UKS2','Key Spelling'),('average','6','KS2','UKS2','Key Spelling'),
    ('definite','6','KS2','UKS2','Key Spelling'),('especially','6','KS2','UKS2','Key Spelling'),
    ('language','6','KS2','UKS2','Key Spelling'),('soldier','6','KS2','UKS2','Key Spelling'),
    ('immediately','6','KS2','UKS2','Key Spelling'),('symbol','6','KS2','UKS2','Key Spelling'),
    ('marvellous','6','KS2','UKS2','Key Spelling'),('twelfth','6','KS2','UKS2','Key Spelling'),
    ('achieve','6','KS2','UKS2','Key Spelling'),('frequently','6','KS2','UKS2','Key Spelling'),
    ('necessary','6','KS2','UKS2','Key Spelling'),('queue','6','KS2','UKS2','Key Spelling'),
    ('recognise','6','KS2','UKS2','Key Spelling'),('equip','6','KS2','UKS2','Key Spelling'),
    ('equipped','6','KS2','UKS2','Key Spelling'),('equipment','6','KS2','UKS2','Key Spelling'),
    ('amateur','6','KS2','UKS2','Key Spelling'),('aggressive','6','KS2','UKS2','Key Spelling'),
    ('communicate','6','KS2','UKS2','Key Spelling'),('appreciate','6','KS2','UKS2','Key Spelling'),
    ('sufficient','6','KS2','UKS2','Key Spelling'),('recommend','6','KS2','UKS2','Key Spelling'),
    ('determined','6','KS2','UKS2','Key Spelling'),('available','6','KS2','UKS2','Key Spelling'),
    ('competition','6','KS2','UKS2','Key Spelling'),('vegetable','6','KS2','UKS2','Key Spelling'),
    ('rhyme','6','KS2','UKS2','Key Spelling'),('rhythm','6','KS2','UKS2','Key Spelling'),
    ('community','6','KS2','UKS2','Key Spelling'),('opportunity','6','KS2','UKS2','Key Spelling'),
    ('hindrance','6','KS2','UKS2','Key Spelling'),('dictionary','6','KS2','UKS2','Key Spelling'),
    ('mischievous','6','KS2','UKS2','Key Spelling'),('secretary','6','KS2','UKS2','Key Spelling'),
    ('apparent','6','KS2','UKS2','Key Spelling'),('lightning','6','KS2','UKS2','Key Spelling'),
    ('foreign','6','KS2','UKS2','Key Spelling'),('bruise','6','KS2','UKS2','Key Spelling'),
    ('embarrass','6','KS2','UKS2','Key Spelling'),('nuisance','6','KS2','UKS2','Key Spelling'),
    ('privilege','6','KS2','UKS2','Key Spelling'),('prejudice','6','KS2','UKS2','Key Spelling'),
    ('committee','6','KS2','UKS2','Key Spelling'),('restaurant','6','KS2','UKS2','Key Spelling'),
    ('cemetery','6','KS2','UKS2','Key Spelling'),('accommodate','6','KS2','UKS2','Key Spelling'),
    ('parliament','6','KS2','UKS2','Key Spelling'),('criticise','6','KS2','UKS2','Key Spelling'),
    ('critic','6','KS2','UKS2','Key Spelling'),('guarantee','6','KS2','UKS2','Key Spelling'),
    ('thorough','6','KS2','UKS2','Key Spelling'),('yacht','6','KS2','UKS2','Key Spelling'),

    # ── Academic / Post-Y6 ────────────────────────────────────────────────
    ('abstract','Post','Post','','Academic'),('academy','Post','Post','','Academic'),('accurate','Post','Post','','Academic'),('acknowledge','Post','Post','','Academic'),('acquire','Post','Post','','Academic'),
    ('adequate','Post','Post','','Academic'),('adjust','Post','Post','','Academic'),('administrate','Post','Post','','Academic'),('affect','Post','Post','','Academic'),('aggregate','Post','Post','','Academic'),
    ('allocate','Post','Post','','Academic'),('alter','Post','Post','','Academic'),('alternative','Post','Post','','Academic'),('amend','Post','Post','','Academic'),('analyse','Post','Post','','Academic'),
    ('approach','Post','Post','','Academic'),('appropriate','Post','Post','','Academic'),('approximate','Post','Post','','Academic'),('aspect','Post','Post','','Academic'),('assess','Post','Post','','Academic'),
    ('assign','Post','Post','','Academic'),('assume','Post','Post','','Academic'),('attach','Post','Post','','Academic'),('attitude','Post','Post','','Academic'),('attribute','Post','Post','','Academic'),
    ('authority','Post','Post','','Academic'),('aware','Post','Post','','Academic'),('benefit','Post','Post','','Academic'),('bond','Post','Post','','Academic'),('capable','Post','Post','','Academic'),
    ('capacity','Post','Post','','Academic'),('challenge','Post','Post','','Academic'),('chapter','Post','Post','','Academic'),('circumstance','Post','Post','','Academic'),('cite','Post','Post','','Academic'),
    ('civil','Post','Post','','Academic'),('clause','Post','Post','','Academic'),('comment','Post','Post','','Academic'),('commission','Post','Post','','Academic'),('commit','Post','Post','','Academic'),
    ('compensate','Post','Post','','Academic'),('complex','Post','Post','','Academic'),('component','Post','Post','','Academic'),('compound','Post','Post','','Academic'),('compute','Post','Post','','Academic'),
    ('concentrate','Post','Post','','Academic'),('concept','Post','Post','','Academic'),('conclude','Post','Post','','Academic'),('conduct','Post','Post','','Academic'),('confer','Post','Post','','Academic'),
    ('conflict','Post','Post','','Academic'),('consent','Post','Post','','Academic'),('consequent','Post','Post','','Academic'),('considerable','Post','Post','','Academic'),('consist','Post','Post','','Academic'),
    ('constant','Post','Post','','Academic'),('constitute','Post','Post','','Academic'),('constrain','Post','Post','','Academic'),('construct','Post','Post','','Academic'),('consult','Post','Post','','Academic'),
    ('consume','Post','Post','','Academic'),('contact','Post','Post','','Academic'),('context','Post','Post','','Academic'),('contract','Post','Post','','Academic'),('contrary','Post','Post','','Academic'),
    ('contrast','Post','Post','','Academic'),('contribute','Post','Post','','Academic'),('convene','Post','Post','','Academic'),('convert','Post','Post','','Academic'),('cooperate','Post','Post','','Academic'),
    ('coordinate','Post','Post','','Academic'),('core','Post','Post','','Academic'),('corporate','Post','Post','','Academic'),('credit','Post','Post','','Academic'),('criteria','Post','Post','','Academic'),
    ('culture','Post','Post','','Academic'),('cycle','Post','Post','','Academic'),('data','Post','Post','','Academic'),('debate','Post','Post','','Academic'),('decline','Post','Post','','Academic'),
    ('deduce','Post','Post','','Academic'),('define','Post','Post','','Academic'),('demonstrate','Post','Post','','Academic'),('design','Post','Post','','Academic'),('despite','Post','Post','','Academic'),
    ('dimension','Post','Post','','Academic'),('discrete','Post','Post','','Academic'),('discriminate','Post','Post','','Academic'),('distinct','Post','Post','','Academic'),('distribute','Post','Post','','Academic'),
    ('diverse','Post','Post','','Academic'),('document','Post','Post','','Academic'),('domain','Post','Post','','Academic'),('domestic','Post','Post','','Academic'),('dominate','Post','Post','','Academic'),
    ('economy','Post','Post','','Academic'),('element','Post','Post','','Academic'),('emerge','Post','Post','','Academic'),('emphasis','Post','Post','','Academic'),('enable','Post','Post','','Academic'),
    ('energy','Post','Post','','Academic'),('enforce','Post','Post','','Academic'),('ensure','Post','Post','','Academic'),('entity','Post','Post','','Academic'),('environment','Post','Post','','Academic'),
    ('equate','Post','Post','','Academic'),('equivalent','Post','Post','','Academic'),('establish','Post','Post','','Academic'),('estate','Post','Post','','Academic'),('estimate','Post','Post','','Academic'),
    ('ethnic','Post','Post','','Academic'),('evaluate','Post','Post','','Academic'),('evident','Post','Post','','Academic'),('evolve','Post','Post','','Academic'),('exceed','Post','Post','','Academic'),
    ('exclude','Post','Post','','Academic'),('expand','Post','Post','','Academic'),('export','Post','Post','','Academic'),('expose','Post','Post','','Academic'),('external','Post','Post','','Academic'),
    ('facilitate','Post','Post','','Academic'),('factor','Post','Post','','Academic'),('feature','Post','Post','','Academic'),('final','Post','Post','','Academic'),('finance','Post','Post','','Academic'),
    ('focus','Post','Post','','Academic'),('formula','Post','Post','','Academic'),('framework','Post','Post','','Academic'),('function','Post','Post','','Academic'),('fund','Post','Post','','Academic'),
    ('fundamental','Post','Post','','Academic'),('generate','Post','Post','','Academic'),('generation','Post','Post','','Academic'),('goal','Post','Post','','Academic'),('grant','Post','Post','','Academic'),
    ('hence','Post','Post','','Academic'),('hypothesis','Post','Post','','Academic'),('identify','Post','Post','','Academic'),('ignorance','Post','Post','','Academic'),('illustrate','Post','Post','','Academic'),
    ('image','Post','Post','','Academic'),('immigrate','Post','Post','','Academic'),('impact','Post','Post','','Academic'),('implement','Post','Post','','Academic'),('implicate','Post','Post','','Academic'),
    ('imply','Post','Post','','Academic'),('impose','Post','Post','','Academic'),('incidence','Post','Post','','Academic'),('income','Post','Post','','Academic'),('indicate','Post','Post','','Academic'),
    ('inhibit','Post','Post','','Academic'),('initial','Post','Post','','Academic'),('injure','Post','Post','','Academic'),('instance','Post','Post','','Academic'),('institute','Post','Post','','Academic'),
    ('integrate','Post','Post','','Academic'),('interact','Post','Post','','Academic'),('internal','Post','Post','','Academic'),('interpret','Post','Post','','Academic'),('invest','Post','Post','','Academic'),
    ('investigate','Post','Post','','Academic'),('involve','Post','Post','','Academic'),('issue','Post','Post','','Academic'),('job','Post','Post','','Academic'),('journal','Post','Post','','Academic'),
    ('justify','Post','Post','','Academic'),('label','Post','Post','','Academic'),('labor','Post','Post','','Academic'),('layer','Post','Post','','Academic'),('legal','Post','Post','','Academic'),
    ('legislate','Post','Post','','Academic'),('liberal','Post','Post','','Academic'),('license','Post','Post','','Academic'),('logic','Post','Post','','Academic'),('maintain','Post','Post','','Academic'),
    ('major','Post','Post','','Academic'),('margin','Post','Post','','Academic'),('maximise','Post','Post','','Academic'),('mechanism','Post','Post','','Academic'),('medical','Post','Post','','Academic'),
    ('mental','Post','Post','','Academic'),('method','Post','Post','','Academic'),('migrate','Post','Post','','Academic'),('minor','Post','Post','','Academic'),('modify','Post','Post','','Academic'),
    ('negate','Post','Post','','Academic'),('network','Post','Post','','Academic'),('normal','Post','Post','','Academic'),('notion','Post','Post','','Academic'),('objective','Post','Post','','Academic'),
    ('obtain','Post','Post','','Academic'),('obvious','Post','Post','','Academic'),('option','Post','Post','','Academic'),('orient','Post','Post','','Academic'),('outcome','Post','Post','','Academic'),
    ('output','Post','Post','','Academic'),('overall','Post','Post','','Academic'),('parallel','Post','Post','','Academic'),('participate','Post','Post','','Academic'),('partner','Post','Post','','Academic'),
    ('perceive','Post','Post','','Academic'),('percent','Post','Post','','Academic'),('period','Post','Post','','Academic'),('perspective','Post','Post','','Academic'),('phase','Post','Post','','Academic'),
    ('philosophy','Post','Post','','Academic'),('policy','Post','Post','','Academic'),('positive','Post','Post','','Academic'),('potential','Post','Post','','Academic'),('precise','Post','Post','','Academic'),
    ('predict','Post','Post','','Academic'),('presume','Post','Post','','Academic'),('previous','Post','Post','','Academic'),('primary','Post','Post','','Academic'),('prime','Post','Post','','Academic'),
    ('principal','Post','Post','','Academic'),('principle','Post','Post','','Academic'),('prior','Post','Post','','Academic'),('proceed','Post','Post','','Academic'),('process','Post','Post','','Academic'),
    ('professional','Post','Post','','Academic'),('project','Post','Post','','Academic'),('promote','Post','Post','','Academic'),('proportion','Post','Post','','Academic'),('psychology','Post','Post','','Academic'),
    ('publish','Post','Post','','Academic'),('purchase','Post','Post','','Academic'),('pursue','Post','Post','','Academic'),('range','Post','Post','','Academic'),('ratio','Post','Post','','Academic'),
    ('react','Post','Post','','Academic'),('regime','Post','Post','','Academic'),('region','Post','Post','','Academic'),('register','Post','Post','','Academic'),('regulate','Post','Post','','Academic'),
    ('require','Post','Post','','Academic'),('research','Post','Post','','Academic'),('reside','Post','Post','','Academic'),('resolve','Post','Post','','Academic'),('resource','Post','Post','','Academic'),
    ('respond','Post','Post','','Academic'),('restrict','Post','Post','','Academic'),('retain','Post','Post','','Academic'),('reveal','Post','Post','','Academic'),('revenue','Post','Post','','Academic'),
    ('scheme','Post','Post','','Academic'),('section','Post','Post','','Academic'),('sector','Post','Post','','Academic'),('secure','Post','Post','','Academic'),('sequence','Post','Post','','Academic'),
    ('series','Post','Post','','Academic'),('shift','Post','Post','','Academic'),('significant','Post','Post','','Academic'),('similar','Post','Post','','Academic'),('source','Post','Post','','Academic'),
    ('specific','Post','Post','','Academic'),('specify','Post','Post','','Academic'),('stable','Post','Post','','Academic'),('statistic','Post','Post','','Academic'),('status','Post','Post','','Academic'),
    ('strategy','Post','Post','','Academic'),('stress','Post','Post','','Academic'),('structure','Post','Post','','Academic'),('style','Post','Post','','Academic'),('subsequent','Post','Post','','Academic'),
    ('substitute','Post','Post','','Academic'),('summary','Post','Post','','Academic'),('supplement','Post','Post','','Academic'),('survey','Post','Post','','Academic'),('sustain','Post','Post','','Academic'),
    ('swarm','Post','Post','','Academic'),('technical','Post','Post','','Academic'),('technique','Post','Post','','Academic'),('technology','Post','Post','','Academic'),('theory','Post','Post','','Academic'),
    ('tradition','Post','Post','','Academic'),('transfer','Post','Post','','Academic'),('transit','Post','Post','','Academic'),('trend','Post','Post','','Academic'),('undertake','Post','Post','','Academic'),
    ('utilise','Post','Post','','Academic'),('valid','Post','Post','','Academic'),('vary','Post','Post','','Academic'),('version','Post','Post','','Academic'),('volume','Post','Post','','Academic'),
    ('welfare','Post','Post','','Academic'),
]

def words_for_year(year):
    return [w for w in WORD_BANK if w[1] == year]

def get_word(index):
    if 0 <= index < len(WORD_BANK):
        return WORD_BANK[index]
    return None

def get_active_words(word_pos, mastered_set, count=5):
    """Return next `count` unmastered words starting from word_pos."""
    active = []
    i = word_pos
    while len(active) < count and i < len(WORD_BANK):
        if WORD_BANK[i][0] not in mastered_set:
            active.append(WORD_BANK[i][0])
        i += 1
    return active

def mastery_stats(mastered_set):
    """Return mastery percentages by year group and phase.

    Y4    = Y4 words only
    LKS2  = Y3 + Y4 (phase)
    KS2   = Y3 + Y4 + Y5 + Y6 (key stage)
    total = all R–Y6 words
    """
    def pct(year):
        words = [w for w in WORD_BANK if w[1] == year]
        if not words:
            return 0
        return round(sum(1 for w in words if w[0] in mastered_set) / len(words) * 100)

    def pct_group(years):
        words = [w for w in WORD_BANK if w[1] in years]
        if not words:
            return 0
        return round(sum(1 for w in words if w[0] in mastered_set) / len(words) * 100)

    return {
        'R':    pct('R'),
        'Y1':   pct('1'),
        'Y2':   pct('2'),
        'Y3':   pct('3'),
        'Y4':   pct('4'),
        'Y5':   pct('5'),
        'Y6':   pct('6'),
        'LKS2':     pct_group(['3','4']),          # Phase: Y3+Y4
        'KS2':      pct_group(['3','4','5','6']), # Key Stage: Y3–Y6
        'Academic': pct('Post'),                  # Post-Y6 academic
        'total':    pct_group(['R','1','2','3','4','5','6']),  # R–Y6 only, excludes Post/Academic
    }


