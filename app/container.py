import injector
from inspect import classify_class_attrs, signature, stack, getmro
from dependencies import __DEPENDENCY

class CircularDependencyError(BaseException):
    pass


class M: # class test
    def __builder(self):
        pass


TYPE_KEY = "type"
DEP_KEY = "dep"
PARAM_NAMES_KEY = "param_name"



def is_subclass_of(cls): return M in getmro(cls)


class Container():

    def __init__(self, D: list[type]) -> None:
        self.app = injector.Injector()
        self.DEPENDENCY = {}
        self.D: set[str] = self.load_baseSet(D)
        self.load_dep(D)
        self.buildContainer()

    def bind(self, type, obj, scope=None):
        self.app.binder.bind(type, to=obj, scope=scope)

    def get(self, type, scope=None): 
        return self.app.get(type, scope)

    def load_dep(self, D):
        for x in D:
            if not self.DEPENDENCY.__contains__(x):
                dep, p = self.getSignature(x)
                self.DEPENDENCY[x.__name__] = {
                    TYPE_KEY: x,
                    DEP_KEY: dep,
                    PARAM_NAMES_KEY: p
                }

    def getSignature(self, t: type):
        params = signature(t).parameters.values()
        l: set[str] = set()
        pn: list[str] = []
        for p in params:
            repr = p.__str__().split(":")
            temp = repr[1].split(".")
            if temp.__len__() == 1:
                # a bug or a warning
                continue
            l.add(temp[1])
            pn.append(repr[0].strip())

        return l, pn

    def load_baseSet(self, D: list[type]):
        t: set[str] = set()
        for d in D:
            t.add(d.__name__)
        return t

    def buildContainer(self):
        while self.D.__len__() != 0:
            no_dep = []
            for x in self.D: 
                d:set[str]= self.DEPENDENCY[x][DEP_KEY]
                if len(d.intersection(self.D))==0:
                    no_dep.append(x)
            if len(no_dep) == 0:
                raise CircularDependencyError
            self.D.difference_update(no_dep)
            for x in no_dep:
                self.inject(x)

    def inject(self, x: str):
        dep: set[str] = self.DEPENDENCY[x][DEP_KEY]
        current_type: type = self.DEPENDENCY[x][TYPE_KEY]
        params_names: list[str] = self.DEPENDENCY[x][PARAM_NAMES_KEY]
        assert len(dep) == len(
            params_names), "The number of dependency must be same length as the number of params names"
        params = {}
        i = 0
        for d in dep:
            obj_dep = self.get(self.DEPENDENCY[d][TYPE_KEY])
            params[params_names[i]] = obj_dep
            i += 1

        obj = self.createDep(current_type, params)
        self.bind(current_type, obj)

    def createDep(self, typ, params):
        flag = is_subclass_of(typ)
        obj = typ(**params)
        if flag:
            obj.__builder()
        else:
            # WARNING raise we cant verify the data provided
            pass
        return obj


CONTAINER: Container = Container(__DEPENDENCY)
print(CONTAINER.D)
