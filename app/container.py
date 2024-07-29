import injector
from inspect import signature, getmro
from dependencies import __DEPENDENCY
from typing import overload, Any
from utils.constant import DEP_KEY, PARAM_NAMES_KEY, RESOLVED_PARAMETER_KEY, RESOLVED_FUNC_KEY, TYPE_KEY, RESOLVED_DEPS_KEY, RESOLVED_CLASS_KEY
from utils.helper import issubclass_of, reverseDict, is_abstract
from services._module import Module, AbstractDependency, AbstractModuleClasses

print(AbstractModuleClasses)

class ContainerError(BaseException): pass

class CircularDependencyError(ContainerError): pass

class MultipleParameterSameDependencyError(ContainerError): pass

class NotSubclassOfAbstractDependencyError(ContainerError): pass

class PrimitiveTypeError(ContainerError): pass

class NotAbstractDependencyError(ContainerError): pass 


def issubclass(cls): return issubclass_of(Module, cls)

def isabstract(cls): return AbstractModuleClasses.__contains__(cls)


class Container():

    def __init__(self, D: list[type]) -> None:
        self.app = injector.Injector()
        self.DEPENDENCY_MetaData = {}
        self.D: set[str] = self.load_baseSet(D)
        self.load_dep(D)
        self.buildContainer()
        self.hashKeyAbsResolving: dict = {}

    def bind(self, type, obj, scope=None):
        self.app.binder.bind(type, to=obj, scope=scope)

    def get(self, type: type, scope=None):
        return self.app.get(type, scope)

    def getFromClassName(self, classname: str, scope=None):
        return self.app.get(self.DEPENDENCY_MetaData[classname][TYPE_KEY], scope)

    def load_dep(self, D: list[type]):
        for x in D:
            if not self.DEPENDENCY_MetaData.__contains__(x):
                dep, p = self.getSignature(x)
                dep = set(dep)
                # ERROR Dependency that is not in the dependency list
                try:
                    abstractRes = self.getAbstractResolving(x)
                    for r in abstractRes.keys():
                        r_dep, r_p = self.getSignature(
                            abstractRes[r][RESOLVED_FUNC_KEY])
                        abstractRes[r][RESOLVED_PARAMETER_KEY] = r_p
                        abstractRes[r][RESOLVED_DEPS_KEY] = r_dep
                        dep = dep.union(r_dep)
                except KeyError as e:
                    pass
                except:
                    pass  # BUG i got an error for real

                self.DEPENDENCY_MetaData[x.__name__] = {
                    TYPE_KEY: x,
                    DEP_KEY: dep,
                    PARAM_NAMES_KEY: p
                }

    def filter(self, D: list[type]):
        temp: list[type] = []
        for dep in D:
            try:
                if issubclass(dep):
                    temp.append(dep)
                else:
                    raise TypeError
            except:  # catch certain type of error
                pass

        return temp

    def getAbstractResolving(self, typ: type):
        return AbstractDependency[typ.__name__]

    def getSignature(self, t: type | Any):
        params = signature(t).parameters.values()
        types: list[str] = [] ## BUG need to verify if theres is a type that already exists
        paramNames: list[str] = []
        for p in params:
            types.append(p.annotation.__name__)
            paramNames.append(p.name)
        return types, paramNames

    def load_baseSet(self, D: list[type]):
        t: set[str] = set()
        for d in D:
            t.add(d.__name__)
        return t

    def buildContainer(self):
        while self.D.__len__() != 0:
            no_dep = []
            for x in self.D:
                d: set[str] = self.DEPENDENCY_MetaData[x][DEP_KEY]
                if len(d.intersection(self.D)) == 0:
                    no_dep.append(x)
            if len(no_dep) == 0:
                raise CircularDependencyError
            self.D.difference_update(no_dep)
            for x in no_dep:
                self.inject(x)

    def inject(self, x: str):
        current_type: type = self.DEPENDENCY_MetaData[x][TYPE_KEY]
        # BUG if abstract class but abstractDependency not empty, we can set for all subclass
        if isabstract(current_type):
            return
        dep: set[str] = self.DEPENDENCY_MetaData[x][DEP_KEY]
        params_names: list[str] = self.DEPENDENCY_MetaData[x][PARAM_NAMES_KEY]
        # VERIFY the number of dependency
        if AbstractDependency.__contains__(x) or self.searchParentClassAbstractDependency(current_type):
            self.resolvedAbsDep(current_type)
            dep = self.switchAbsDep(current_type, dep)
        params = self.toParams(dep, params_names)
        obj = self.createDep(current_type, params)
        self.bind(current_type, obj)

    def searchParentClassAbstractDependency(self,currentType:type):
        parentClasses:list[type] = list(getmro(currentType))
        parentClasses.pop(0)
        for x in parentClasses:
            if x.__name__ in AbstractDependency.keys():
                self.hashKeyAbsResolving[currentType.__name__] = x
                return True
        return False
        # for x in AbstractDependency:
        #     absDepKeyClass = AbstractModuleClasses[x]
        #     if issubclass_of( absDepKeyClass,currentType): 
        #         self.hashKeyAbsResolving[currentType.__name__] = x  
        #         return True
        # return False
        
    def switchAbsDep(self, current_type: type, dependencies: set[str]):
        if len(dependencies) == 0:
            return set()
        try:
            temp = list(dependencies)
            print(temp)

            for absClassname, resolvedClass in AbstractDependency[self.hashAbsDep(current_type.__name__)].items():
                if resolvedClass[RESOLVED_CLASS_KEY]:
                    index = temp.index(absClassname)
                    del temp[index]
                    temp.insert(
                        index, resolvedClass[RESOLVED_CLASS_KEY].__name__)
            return set(temp)
        except ValueError as e:
            pass
        except KeyError as e:
            # BUG: handle the case where the dependency cannot be resolved
            pass
 
    def resolvedAbsDep(self, current_type: type):  # ERROR gerer les erreur des if
        try:
            if issubclass(current_type):
                pass
            for absClassName, absResolving in AbstractDependency[self.hashAbsDep(current_type.__name__)].items():
                absClass = AbstractModuleClasses[absClassName]
                if not isabstract(absClass):
                    pass
                absResParams = {}
                if absResolving[RESOLVED_PARAMETER_KEY] is not None:
                    absResParams = self.toParams(
                        absResolving[RESOLVED_DEPS_KEY], absResolving[RESOLVED_PARAMETER_KEY])

                resolvedDep = absResolving[RESOLVED_FUNC_KEY](
                    **absResParams)
                if not isinstance(resolvedDep, type):
                    pass
                if not issubclass_of(absClass, resolvedDep):
                    pass
                if not issubclass(resolvedDep):
                    pass
                absResolving[RESOLVED_CLASS_KEY] = resolvedDep

        except NameError:
            pass
        except TypeError:
            pass
        return current_type

    def toParams(self, dep, params_names):
        params = {}
        i = 0
        for d in dep:
            obj_dep = self.get(self.DEPENDENCY_MetaData[d][TYPE_KEY])
            params[params_names[i]] = obj_dep
            i += 1
        return params

    def createDep(self, typ, params):
        flag = issubclass(typ)
        obj: Module = typ(**params)
        if flag:
            obj._builder()
        else:
            # WARNING raise we cant verify the data provided
            pass
        return obj

    @property
    def objectDependencies(self):
        return []

    @property
    def dependencies(self) -> list[type]: return [x[TYPE_KEY]
                                                  for x in self.DEPENDENCY_MetaData.values()]

    @property
    def hashAbsDep(self,cls: str):
        return cls if not self.hashKeyAbsResolving.__contains__(cls) else self.hashKeyAbsResolving[cls]

CONTAINER: Container = Container(__DEPENDENCY)


def InjectInFunction(func):
    """
    The `InjectInFunction` decorator takes the function and inspect it's signature, if the `CONTAINER` can resolve the 
    dependency it will inject the values. You must call the function with the position parameter format to call 
    the `func` with the rest of the parameters.

    If the parameters of the function founds a dependency two times it will return an error

    `example:: `

    @InjectInFunction
    def test(a: A, b: B, c: C, s:str):
        print(a)
        print(b)
        print(c)
        print(s)

    >>> test(s="ok")
    >>> <__main__.C object at 0x000001A76EC36610>
        <__main__.B object at 0x000001A76EC36810>
        <__main__.A object at 0x000001A76EC3FB90>
        ok
    """
    types, paramNames = CONTAINER.getSignature(func)
    paramsToInject = CONTAINER.toParams(types, paramNames)
    def wrapper(*args, **kwargs):
        # revparams = reverseDict(paramsToInject)
        paramsToInject.update(kwargs)
        func(**paramsToInject)
    return wrapper


