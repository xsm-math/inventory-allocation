"""Native HiGHS adapter with a checked MIP start and incumbent preservation."""
import numpy as np
from scipy.optimize import OptimizeResult


def valid_vector(model,matrix,value):
    v=np.asarray(value,float)
    if v.shape!=(len(model.c),) or not np.isfinite(v).all():return False
    lower=np.asarray(model.lower,float);upper=np.asarray(model.ub,float)
    if np.any(v<lower-1e-5) or np.any(v>upper+1e-5):return False
    lhs=matrix@v
    if np.any(lhs<np.asarray(model.lo)-1e-5) or np.any(lhs>np.asarray(model.hi)+1e-5):return False
    integer=np.asarray(model.integer,bool)
    return bool(np.all(np.abs(v[integer]-np.rint(v[integer]))<=1e-5))


def solve_native(model,matrix,time_limit,gap,absolute_gap=None):
    try:
        import highspy
    except ImportError as exc:
        raise RuntimeError('Native backend requires the pinned highspy dependency') from exc
    h=highspy.Highs()
    options={'output_flag':False,'threads':1,'random_seed':0,
             'time_limit':float(time_limit),'mip_rel_gap':float(gap)}
    if absolute_gap is not None:options['mip_abs_gap']=float(absolute_gap)
    for name,value in options.items():
        if h.setOptionValue(name,value)!=highspy.HighsStatus.kOk:
            raise ValueError(f'Native solver rejected option {name}')
    lp=highspy.HighsLp()
    lp.num_col_=len(model.c);lp.num_row_=len(model.lo)
    lp.col_cost_=np.asarray(model.c,float);lp.col_lower_=np.asarray(model.lower,float)
    lp.col_upper_=np.asarray(model.ub,float)
    lp.row_lower_=np.asarray(model.lo,float);lp.row_upper_=np.asarray(model.hi,float)
    lp.a_matrix_.format_=highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_=matrix.indptr.astype(np.int32)
    lp.a_matrix_.index_=matrix.indices.astype(np.int32)
    lp.a_matrix_.value_=matrix.data
    lp.integrality_=[highspy.HighsVarType.kInteger if x else highspy.HighsVarType.kContinuous for x in model.integer]
    if h.passModel(lp)!=highspy.HighsStatus.kOk:
        raise RuntimeError('Native solver rejected model')
    start=getattr(model,'mip_start',None)
    if start is not None:
        start=np.asarray(start,float).copy()
        if not valid_vector(model,matrix,start):
            raise ValueError('Invalid MIP start')
        status=h.setSolution(len(start),np.arange(len(start),dtype=np.int32),start)
        if status!=highspy.HighsStatus.kOk:
            raise RuntimeError('Native solver rejected checked MIP start')
    h.run()
    native_status=h.getModelStatus();info=h.getInfo();solution=h.getSolution()
    codes={highspy.HighsModelStatus.kOptimal:0,highspy.HighsModelStatus.kTimeLimit:1,
           highspy.HighsModelStatus.kIterationLimit:1,highspy.HighsModelStatus.kSolutionLimit:1,
           highspy.HighsModelStatus.kObjectiveBound:1,highspy.HighsModelStatus.kObjectiveTarget:1,
           highspy.HighsModelStatus.kInterrupt:1,highspy.HighsModelStatus.kInfeasible:2,
           highspy.HighsModelStatus.kUnbounded:3}
    code=codes.get(native_status,4)
    candidate=np.asarray(solution.col_value,float) if solution.value_valid else None
    if candidate is not None and not valid_vector(model,matrix,candidate):candidate=None
    cost=np.asarray(model.c,float)
    retained=False
    if start is not None and (candidate is None or cost@start<cost@candidate-1e-7):
        candidate=start;retained=True
    objective=float(cost@candidate) if candidate is not None else None
    bound=float(info.mip_dual_bound) if info.valid and code in (0,1) and np.isfinite(info.mip_dual_bound) else None
    if bound is not None and objective is not None and bound>objective+1e-5:bound=None
    if start is not None and code in (2,3):
        code=4;bound=None
    absolute=max(0.,objective-bound) if objective is not None and bound is not None else None
    relative=absolute/max(abs(objective),1e-12) if absolute is not None else None
    result=OptimizeResult(x=candidate,fun=objective,status=code,
        message=h.modelStatusToString(native_status),mip_gap=relative,mip_dual_bound=bound,
        mip_absolute_gap=absolute,solver_backend='highs',solver_version=h.version(),
        warm_start_submitted=start is not None,start_retained=retained,
        warm_start_objective=float(cost@start) if start is not None else None)
    return result
