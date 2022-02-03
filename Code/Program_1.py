#%%
# liberaries
from matplotlib.font_manager import list_fonts
import mysql.connector
from mysql.connector import errorcode
import json
from os.path import dirname, abspath
import pandas as pd
from pprint import pprint

# defining variables
input_folder = "\Input\\"
file_name = "key.json"
organism = 'escherichia coli'
ec_number = "5.3.1.9"
dir = dirname(dirname(abspath(__file__))) 
input_dir = dir + input_folder
key = input_dir + file_name
logfile = dir + "\log.txt"

# defining functions
def NoDuplicates(seq, idfun=None): 
   # order preserving
   if idfun is None:
       def idfun(x): return x
   seen = {}
   result = []
   for item in seq:
       marker = idfun(item)
       # in old Python versions:
       # if seen.has_key(marker)
       # but in new ones:
       if marker in seen: continue
       seen[marker] = 1
       result.append(item)
   return result

# connect to mysql and return cursor
def connect_to_mysql():
    with open(key) as jsonfile:
        data = json.load(jsonfile)
    try:
        cnx = mysql.connector.connect(user=data["user"],password=data["password"],host=data["host"],database=data["database"])
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Something is wrong with your user name or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Database does not exist")
        else:
            print(err)
    return cnx

# defining classes
class Organism:
    def __init__(self, name, cid=[] ,iid=[],uid=[], strv = [], comment = [], res=[]):
        print("constucting {}".format(name))
        self.name       = name
        self.cid        = cid
        self.iid        = iid
        self.uid        = uid
        self.strv       = strv
        self.res        = res
        self.comment    = comment

    def get_db_info(self,query, parameters):
        self.cnx        = connect_to_mysql()
        cursor          = self.cnx.cursor()
        try:
            cursor.execute(query, parameters)
            row         = cursor.fetchone()
            while row  != None:
                self.res.append(row)
                row     = cursor.fetchone()
        except Exception as a:
            print("Something is wrong in the query:")
            print(a)
            print("Mysql warnings:")
            print(cursor._fetch_warnings())
            print("executed query:")
            print(cursor._executed)
            self.cnx.close()

        if not self.res:
            print("no results for {}".format(self.name))
            print("executed query:")
            print(cursor._executed)
            exit()

    def close_connection(self):
        self.cnx.close()

    def load_results_into_object(self):
        self.cid        = [self.res[i][0] for i in range(len(self.res))]
        self.iid        = [self.res[i][1] for i in range(len(self.res))]
        self.uid        = [self.res[i][2] for i in range(len(self.res))]

    def print_results(self):
        print("results for {} are: \n {}".format(self.name, self.res))

class EC_number(Organism):
    def __init__(self, name, cid=[] ,iid=[],uid=[], strv = [], comment = [],res=[]):
        super().__init__(name,cid,iid,uid,strv,comment,res )

class Activator(Organism):
    def __init__(self, name, cid=[] ,iid=[],uid=[], strv = [], comment = [], res=[]):
        super().__init__(name,cid,iid,uid,strv,comment,res)

    def load_results_into_object(self):
        super().load_results_into_object()
        self.strv       = [self.res[i][3] for i in range(len(self.res))]
        self.comment    = [self.res[i][4] for i in range(len(self.res))]
    
    def cleared_result(self):
        results         = {}
        unique_set      = NoDuplicates(self.uid)
        results["uid"]  = self.uid
        results["cid"]  = self.cid
        results["iid"]  = self.iid
        results["strv"] = self.strv
        results["lstrv"]= [len(item) for item in self.strv]
        results["tag"]  = self.comment
        df = pd.DataFrame.from_dict(results)
        res_df = pd.DataFrame(data = None, columns= df.columns)

        for i in range(len(unique_set)):
            lenmin      = min(df.loc[(df.uid == unique_set[i]), "lstrv"].values)
            temp_df     = df.loc[ (df.uid==unique_set[i]) & (df.lstrv == lenmin)]
            minin       = min(temp_df.index)
            res_df      = res_df.append(temp_df.loc[minin,:])
        return res_df

#  Function main_analyze  
def main_analyze(ec_name, organism_name):
    # constructing object for organism
    query = ("""select distinct cid,iid, uid from main where uid in 
    (select refv from main where refv in (select uid from main 
    where cid =1 and refv = 0) and strv = %s)""")
    parameter           = (organism_name,)
    O_obj               = Organism(organism)
    O_obj.get_db_info(query,parameter)
    O_obj.load_results_into_object()
    O_obj.print_results()
    O_obj.close_connection()
    
    # constructing EC Object
    query = ("""select distinct cid, iid, uid from main where 
    uid in (select refv from main where refv in 
    (select uid from main where cid = 2 and refv = 0) 
    and iid = 17 and strv = %s)""")
    parameter           = (ec_name,)
    ec_obj              = EC_number(ec_number)
    ec_obj.get_db_info(query,parameter)
    ec_obj.load_results_into_object()
    ec_obj.print_results()
    ec_obj.close_connection()

    # inhibitor uid
    query = (
    """select distinct t1.cid,t1.iid,t1.uid, t3.strv,
    if(t4.iid=10,"Inhibitor",if(t4.iid=11,"Activator", if(t4.iid=12,"Cofactor","Else"))) 
    from main as t1 
    join main as t2 
    on t2.cid=t1.cid and t2.iid = t1.iid
    join main as t3
    on t3.refv = t2.uid
    join main as t4
    on t4.refv = t1.uid
    where t1.refv in 
    (select uid from main where refv in 
    (select uid from main where refv in 
    (select uid from main where cid = 6 and iid = 1 and refv = %s ) 
    and cid = %s and iid = %s) and cid = 6 and iid = 1)
    and t2.refv = 0 and t3.cid = 5 AND t3.iid in (1,2,3)
    order by uid, CHAR_LENGTH(t3.strv) ASC
"""
    )
    parameter           = (O_obj.uid[0],ec_obj.cid[0],ec_obj.iid[0])
    param_obj           = Activator("activators")
    param_obj.get_db_info(query,parameter)
    param_obj.load_results_into_object()
    param_obj.close_connection()
    dic = param_obj.cleared_result()
    print("run",file=open(logfile, "a"))
    print(dic,file=open(logfile, "a"))
    print(dic)

main_analyze(ec_number, organism)

 
    
# %%
