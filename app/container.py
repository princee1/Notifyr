import injector
from inspect import signature, getmro
from dependencies import __DEPENDENCY
from typing import Callable, Any
from utils.constant import DependencyConstant
from utils.helper import issubclass_of, SkipCode
from services._service import Service, AbstractDependency, AbstractServiceClasses, BuildOnlyIfDependencies, PossibleDependencies
from utils.prettyprint import printJSON
from typing import TypeVar

T = TypeVar('T', bound=Service)


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


class NotBoolBuildOnlyDependencyError(ContainerError):
    pass


class NotAbstractDependencyError(ContainerError):
    pass  # Abstract Class not specified


class NoResolvedDependencyError(ContainerError):
    pass  # Cannot resolved a subclass for a parent class


class NotInDependenciesError(ContainerError):
    pass  # SubClass not in the Dependencies list


class InvalidDependencyError(ContainerError):
    pass  # Abstract class in the dependency list


def issubclass(cls): return issubclass_of(Service, cls)


def isabstract(cls): 
    """
    The function `isabstract` checks if a class is in the set `AbstractServiceClasses`.
    
    :param cls: The `cls` parameter in the `isabstract` function is typically used to represent a class
    that you want to check for abstractness. The function checks if the provided class is in the
    `AbstractServiceClasses` collection to determine if it is an abstract service class
    :return: The function `isabstract(cls)` returns whether the class `cls` is contained within the set
    `AbstractServiceClasses`.
    """
    return AbstractServiceClasses.__contains__(cls)


class Container():

    def __init__(self, D: list[type]) -> None: #TODO add the scope option
        self.__app = injector.Injector()
        self.DEPENDENCY_MetaData = {}
        self.__hashKeyAbsResolving: dict = {}
        self.__D: set[str] = self.__load_baseSet(D)
        self.__load_dep(D)
        self.__buildContainer()
        self.__freeUpMemory()
        # TODO print success  in building the app

    def __bind(self, type, obj, scope=None):
        self.__app.binder.bind(type, to=obj, scope=scope)

    def get(self, typ: type, scope=None, all=False) -> dict[type, T] | T:
        if not all and isabstract(typ.__name__):
            raise InvalidDependencyError

        if all and isabstract(typ.__name__):
            provider: dict[type, T] = {}
            for d in self.dependencies:
                if issubclass_of(typ, d):
                    provider[d] = self.__app.get(d, scope)
            return provider

        return self.__app.get(typ, scope)

    def getFromClassName(self, classname: str, scope=None):
        return self.__app.get(self.DEPENDENCY_MetaData[classname][DependencyConstant.TYPE_KEY], scope)

    def __load_dep(self, D: list[type]):
        for x in D:
            if not self.DEPENDENCY_MetaData.__contains__(x):
                dep_param_list, p = self.getSignature(x)
                dep = set(dep_param_list)

                try:
                    depNotInjected = dep.difference(self.__D)
                    if len(depNotInjected) != 0:
                        for y in depNotInjected:
                            if y not in AbstractServiceClasses:
                                raise NotInDependenciesError
                    abstractRes = self.__getAbstractResolving(x)
                    for r in abstractRes.keys():
                        r_dep, r_p = self.getSignature(
                            abstractRes[r][DependencyConstant.RESOLVED_FUNC_KEY])
                        abstractRes[r][DependencyConstant.RESOLVED_PARAMETER_KEY] = r_p
                        abstractRes[r][DependencyConstant.RESOLVED_DEPS_KEY] = r_dep
                        dep = dep.union(r_dep)
                except KeyError as e:
                    pass

                try:
                    possible_dep = set(PossibleDependencies[x.__name__])
                    dep = dep.union(possible_dep)
                except KeyError:  # NOTE possible dependencies keys does not exists
                    pass
                except:
                    pass

                flag: bool = True
                try:
                    injectOnlyData = BuildOnlyIfDependencies[x.__name__]
                    flag = injectOnlyData[DependencyConstant.BUILD_ONLY_FLAG_KEY]
                    if flag is not None:
                        if flag:
                            dep.add(
                                injectOnlyData[DependencyConstant.BUILD_ONLY_CLASS_KEY])
                            raise SkipCode  # NOTE skip further line of code

                    inject_only_dep, inject_only_params = self.getSignature(
                        injectOnlyData[DependencyConstant.BUILD_ONLY_FUNC_KEY])
                    injectOnlyData[DependencyConstant.BUILD_ONLY_DEP_KEY] = inject_only_dep
                    injectOnlyData[DependencyConstant.BUILD_ONLY_PARAMS_KEY] = inject_only_params
                    dep = dep.union(set(inject_only_dep))
                except SkipCode as e:
                    pass
                except:
                    pass

                self.DEPENDENCY_MetaData[x.__name__] = {
                    DependencyConstant.TYPE_KEY: x,
                    DependencyConstant.DEP_KEY: dep,
                    DependencyConstant.PARAM_NAMES_KEY: p,
                    DependencyConstant.DEP_PARAMS_KEY: dep_param_list,
                    # NOTE the flag might be None, if it is indeed i need to check the func
                    DependencyConstant.FLAG_BUILD_KEY: flag
                }

    def __filter(self, D: list[type]):
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

    def __getAbstractResolving(self, typ: type):
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

    def __load_baseSet(self, D: list[type]):
        t: set[str] = set()
        for d in D:
            if isabstract(d.__name__):
                raise InvalidDependencyError
            t.add(d.__name__)
        return t

    def __buildContainer(self):
        while self.__D.__len__() != 0:
            no_dep = []
            for x in self.__D:
                d: set[str] = self.DEPENDENCY_MetaData[x][DependencyConstant.DEP_KEY]
                if len(d.intersection(self.__D)) == 0:
                    no_dep.append(x)
            if len(no_dep) == 0:
                raise CircularDependencyError
            self.__D.difference_update(no_dep)
            for x in no_dep:
                self.__inject(x)

    def __inject(self, x: str):
        current_type: type = self.DEPENDENCY_MetaData[x][DependencyConstant.TYPE_KEY]
        if isabstract(current_type):
            return
        dep: list[str] = self.DEPENDENCY_MetaData[x][DependencyConstant.DEP_PARAMS_KEY]
        params_names: list[str] = self.DEPENDENCY_MetaData[x][DependencyConstant.PARAM_NAMES_KEY]
        # VERIFY the number of dependency
        if AbstractDependency.__contains__(x) or self.__searchParentClassAbstractDependency(current_type):
            self.__resolvedAbsDep(current_type)
            dep = self.__switchAbsDep(current_type, dep)
        # BUG might need to call before the abstract resolving
        self.__resolve_buildOnly(x)
        params = self.toParams(dep, params_names)
        obj = self.__createDep(current_type, params)
        self.__bind(current_type, obj)

    def __resolve_buildOnly(self, dep_name: str):
        if dep_name in BuildOnlyIfDependencies and BuildOnlyIfDependencies[dep_name][DependencyConstant.BUILD_ONLY_FLAG_KEY] is None:
            func = BuildOnlyIfDependencies[dep_name][DependencyConstant.BUILD_ONLY_FUNC_KEY]
            bOnlyDep, bOnlyParamNames = self.getSignature(func)
            BuildOnlyIfDependencies[dep_name][DependencyConstant.BUILD_ONLY_DEP_KEY] = bOnlyDep
            BuildOnlyIfDependencies[dep_name][DependencyConstant.BUILD_ONLY_PARAMS_KEY] = bOnlyParamNames
            params = self.toParams(bOnlyDep, bOnlyParamNames)
            flag = func(**params)
            if type(flag) != bool:
                raise NotBoolBuildOnlyDependencyError
            self.DEPENDENCY_MetaData[dep_name][DependencyConstant.FLAG_BUILD_KEY] = flag

    def __searchParentClassAbstractDependency(self, currentType: type):
        parentClasses: list[type] = list(getmro(currentType))
        parentClasses.pop(0)
        for x in parentClasses:
            if x.__name__ in AbstractDependency.keys():
                self.__hashKeyAbsResolving[currentType.__name__] = x
                return True
        return False
        # for x in AbstractDependency:
        #     absDepKeyClass = AbstractModuleClasses[x]
        #     if issubclass_of( absDepKeyClass,currentType):
        #         self.hashKeyAbsResolving[currentType.__name__] = x
        #         return True
        # return False

    def __switchAbsDep(self, current_type: type, dependencies: list[str]):
        if len(dependencies) == 0:
            return []
        try:
            for absClassname, resolvedClass in AbstractDependency[self.hashAbsDep(current_type.__name__)].items():
                if resolvedClass[DependencyConstant.RESOLVED_CLASS_KEY]:
                    index = dependencies.index(absClassname)
                    del dependencies[index]
                    dependencies.insert(
                        index, resolvedClass[DependencyConstant.RESOLVED_CLASS_KEY].__name__)
            return dependencies
        except ValueError as e:
            pass
        except KeyError as e:
            # BUG: handle the case where the dependency cannot be resolved
            pass

    def __resolvedAbsDep(self, current_type: type):
        try:
            if issubclass(current_type):
                pass
            for absClassName, absResolving in AbstractDependency[self.hashAbsDep(current_type.__name__)].items():
                absClass = AbstractServiceClasses[absClassName]
                if not isabstract(absClass):
                    raise NotAbstractDependencyError
                absResParams = {}
                if absResolving[DependencyConstant.RESOLVED_PARAMETER_KEY] is not None:
                    absResParams = self.toParams(
                        absResolving[DependencyConstant.RESOLVED_DEPS_KEY], absResolving[DependencyConstant.RESOLVED_PARAMETER_KEY])

                resolvedDep = absResolving[DependencyConstant.RESOLVED_FUNC_KEY](
                    **absResParams)
                if not isinstance(resolvedDep, type):
                    raise TypeError  # suppose to be an instance of type

                if not issubclass_of(absClass, resolvedDep):
                    raise NotSubclassOfAbstractDependencyError

                if not issubclass(resolvedDep):
                    # WARNING: This might create problem
                    pass
                absResolving[DependencyConstant.RESOLVED_CLASS_KEY] = resolvedDep

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
                obj_dep = self.get(
                    self.DEPENDENCY_MetaData[d][DependencyConstant.TYPE_KEY])
                params[params_names[i]] = obj_dep
                i += 1
            return params
        except KeyError:
            raise NoResolvedDependencyError

    def __createDep(self, typ: type, params):
        flag = issubclass(typ)
        obj: Service = typ(**params)

        if flag:
            willBuild = self.DEPENDENCY_MetaData[typ.__name__][DependencyConstant.FLAG_BUILD_KEY]
            if willBuild:
                obj._builder()  # create the dependency but not calling the builder
        else:
            # WARNING raise we cant verify the data provided
            pass
        return obj

    def __freeUpMemory(self):
        for k, v in self.DEPENDENCY_MetaData.items():
            del v[DependencyConstant.PARAM_NAMES_KEY]

        for k, v in BuildOnlyIfDependencies.items():
            del v[DependencyConstant.BUILD_ONLY_PARAMS_KEY]

        # TODO free up temp variable
        pass

    def need(self, typ: type) -> T:
        if not self.DEPENDENCY_MetaData[typ.__name__][DependencyConstant.BUILD_ONLY_FLAG_KEY]:
            dependency: Service = self.get(typ)
            try:
                dependency._builder()
                return dependency
            except:
                pass
        return self.get(typ)

    def destroyAllDependency(self,scope = None):
        raise NotImplementedError
        for dep in __DEPENDENCY:
            self.destroyDep(dep,scope)
            
    def destroyDep(self,typ: type, scope = None):
        D = self.__app.get(typ, scope)
        if issubclass(D): #BUG need to ensure that this a Service type
            D:Service = D # NOTE access to the intellisense
            D._destroyer()
    
    def reloadDep(self,typ:type, scope=None):
        pass
    
    @property
    def dependencies(self) -> list[type]: return [x[DependencyConstant.TYPE_KEY]
                                                  for x in self.DEPENDENCY_MetaData.values()]  # TODO avoid to compute this everytime we call this function

    @property
    def objectDependencies(self):
        return [self.get(d) for d in self.dependencies]

    @property
    def hashAbsDep(self, cls: str):
        return cls if not self.__hashKeyAbsResolving.__contains__(cls) else self.__hashKeyAbsResolving[cls]


CONTAINER: Container = Container(__DEPENDENCY)

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
