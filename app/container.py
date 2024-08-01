import injector
from inspect import signature, getmro
from dependencies import __DEPENDENCY
from typing import Callable, Any
from utils.constant import ConstantDependency
from utils.helper import issubclass_of
from services._module import Module, AbstractDependency, AbstractModuleClasses
from utils.prettyprint import printDictJSON


class ContainerError(BaseException):
    pass


class CircularDependencyError(ContainerError):
    pass


class MultipleParameterSameDependencyError(ContainerError):
    pass


class NotSubclassOfAbstractDependencyError(ContainerError):
    pass  # The resolved class is not a subclass of the Base Class we wanted to resolve


class PrimitiveTypeError(ContainerError):
    pass


class NotAbstractDependencyError(ContainerError):
    pass  # Abstract Class not specified


class NoResolvedDependencyError(ContainerError):
    pass  # Cannot resolved a subclass for a parent class


class NotInDependenciesError(ContainerError):
    pass  # SubClass not in the Dependencies list


class InvalidDependencyError(ContainerError):
    pass  # Abstract class in the dependency list


def issubclass(cls): return issubclass_of(Module, cls)


def isabstract(cls): return AbstractModuleClasses.__contains__(cls)


class Container():

    def __init__(self, D: list[type]) -> None:
        self.app = injector.Injector()
        self.DEPENDENCY_MetaData = {}
        self.hashKeyAbsResolving: dict = {}
        # TODO append the dependency needed but might not be in the Dependencies list
        self.D: set[str] = self.load_baseSet(D)
        self.load_dep(D)
        self.buildContainer()
        # TODO print success  in building the app

    def bind(self, type, obj, scope=None):
        self.app.binder.bind(type, to=obj, scope=scope)

    def get(self, typ: type, scope=None, all=False):
        if not all and isabstract(typ.__name__):
            raise InvalidDependencyError

        if all and isabstract(typ.__name__):
            provider: dict[type, object] ={}
            for d in self.dependencies:
                if issubclass_of(typ, d):
                    provider[d] = self.app.get(d,scope)
            return provider

        return self.app.get(typ, scope)

    def getFromClassName(self, classname: str, scope=None):
        return self.app.get(self.DEPENDENCY_MetaData[classname][ConstantDependency.TYPE_KEY], scope)

    def load_dep(self, D: list[type]):
        for x in D:
            if not self.DEPENDENCY_MetaData.__contains__(x):
                dep_list, p = self.getSignature(x)
                dep = set(dep_list)

                try:
                    depNotInjected = dep.difference(self.D)
                    if len(depNotInjected) != 0:
                        for y in depNotInjected:
                            if y not in AbstractModuleClasses:
                                raise NotInDependenciesError
                    abstractRes = self.getAbstractResolving(x)
                    for r in abstractRes.keys():
                        r_dep, r_p = self.getSignature(
                            abstractRes[r][ConstantDependency.RESOLVED_FUNC_KEY])
                        abstractRes[r][ConstantDependency.RESOLVED_PARAMETER_KEY] = r_p
                        abstractRes[r][ConstantDependency.RESOLVED_DEPS_KEY] = r_dep
                        dep = dep.union(r_dep)
                except KeyError as e:
                    pass

                self.DEPENDENCY_MetaData[x.__name__] = {
                    ConstantDependency.TYPE_KEY: x,
                    ConstantDependency.DEP_KEY: dep,
                    ConstantDependency.PARAM_NAMES_KEY: p,
                    ConstantDependency.DEP_PARAMS_KEY: dep_list
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

    def getSignature(self, t: type | Callable):
        params = signature(t).parameters.values()
        types: list[str] = []
        paramNames: list[str] = []
        for p in params:
            if types.count(p.annotation.__name__) == 1:
                raise MultipleParameterSameDependencyError

            types.append(p.annotation.__name__)
            paramNames.append(p.name)

        return types, paramNames

    def load_baseSet(self, D: list[type]):
        t: set[str] = set()
        for d in D:
            if isabstract(d.__name__):
                raise InvalidDependencyError
            t.add(d.__name__)
        return t

    def buildContainer(self):
        while self.D.__len__() != 0:
            no_dep = []
            for x in self.D:
                d: set[str] = self.DEPENDENCY_MetaData[x][ConstantDependency.DEP_KEY]
                if len(d.intersection(self.D)) == 0:
                    no_dep.append(x)
            if len(no_dep) == 0:
                raise CircularDependencyError
            self.D.difference_update(no_dep)
            for x in no_dep:
                self.inject(x)

    def inject(self, x: str):
        current_type: type = self.DEPENDENCY_MetaData[x][ConstantDependency.TYPE_KEY]
        if isabstract(current_type):
            return
        dep: list[str] = self.DEPENDENCY_MetaData[x][ConstantDependency.DEP_PARAMS_KEY]
        params_names: list[str] = self.DEPENDENCY_MetaData[x][ConstantDependency.PARAM_NAMES_KEY]
        # VERIFY the number of dependency
        if AbstractDependency.__contains__(x) or self.searchParentClassAbstractDependency(current_type):
            self.resolvedAbsDep(current_type)
            dep = self.switchAbsDep(current_type, dep)
        params = self.toParams(dep, params_names)
        obj = self.createDep(current_type, params)
        self.bind(current_type, obj)

    def searchParentClassAbstractDependency(self, currentType: type):
        parentClasses: list[type] = list(getmro(currentType))
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

    def switchAbsDep(self, current_type: type, dependencies: list[str]):
        if len(dependencies) == 0:
            return []
        try:
            for absClassname, resolvedClass in AbstractDependency[self.hashAbsDep(current_type.__name__)].items():
                if resolvedClass[ConstantDependency.RESOLVED_CLASS_KEY]:
                    index = dependencies.index(absClassname)
                    del dependencies[index]
                    dependencies.insert(
                        index, resolvedClass[ConstantDependency.RESOLVED_CLASS_KEY].__name__)
            return dependencies
        except ValueError as e:
            pass
        except KeyError as e:
            # BUG: handle the case where the dependency cannot be resolved
            pass

    def resolvedAbsDep(self, current_type: type):
        try:
            if issubclass(current_type):
                pass
            for absClassName, absResolving in AbstractDependency[self.hashAbsDep(current_type.__name__)].items():
                absClass = AbstractModuleClasses[absClassName]
                if not isabstract(absClass):
                    raise NotAbstractDependencyError
                absResParams = {}
                if absResolving[ConstantDependency.RESOLVED_PARAMETER_KEY] is not None:
                    absResParams = self.toParams(
                        absResolving[ConstantDependency.RESOLVED_DEPS_KEY], absResolving[ConstantDependency.RESOLVED_PARAMETER_KEY])

                resolvedDep = absResolving[ConstantDependency.RESOLVED_FUNC_KEY](
                    **absResParams)
                if not isinstance(resolvedDep, type):
                    raise TypeError  # suppose to be an instance of type

                if not issubclass_of(absClass, resolvedDep):
                    raise NotSubclassOfAbstractDependencyError

                if not issubclass(resolvedDep):
                    # WARNING: This might create problem
                    pass
                absResolving[ConstantDependency.RESOLVED_CLASS_KEY] = resolvedDep

        except NameError:
            pass
        except TypeError:
            pass
        except KeyError:
            pass
        return current_type

    def toParams(self, dep, params_names):
        try:
            params = {}
            i = 0
            for d in dep:
                obj_dep = self.get(self.DEPENDENCY_MetaData[d][ConstantDependency.TYPE_KEY])
                params[params_names[i]] = obj_dep
                i += 1
            return params
        except KeyError:
            raise NoResolvedDependencyError

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
    def dependencies(self) -> list[type]: return [x[ConstantDependency.TYPE_KEY]
                                                  for x in self.DEPENDENCY_MetaData.values()]  # TODO avoid to compute this everytime we call this function

    @property
    def objectDependencies(self):
        return [self.get(d) for d in self.dependencies]

    @property
    def hashAbsDep(self, cls: str):
        return cls if not self.hashKeyAbsResolving.__contains__(cls) else self.hashKeyAbsResolving[cls]


CONTAINER: Container = Container(__DEPENDENCY)
printDictJSON(CONTAINER.DEPENDENCY_MetaData, indent=2)


def InjectInFunction(func: Callable):
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
        paramsToInject.update(kwargs)
        func(**paramsToInject)
    return wrapper
