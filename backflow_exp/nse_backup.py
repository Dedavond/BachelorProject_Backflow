from dolfin import *
import numpy as np
import matplotlib.pyplot as plt
import scipy as sp
import scipy.sparse.linalg as ssl
from numpy import linalg as LA
import progress as prog
import HelperFuncs as HF


def nse(Re=1000, temam=False, bfs=False, level=1, velocity_degree=2, eps=0.0002, dt=0.001, auto=False, plotcircles=0, gammagiv=1):

    mesh_root = 'stenosis_f0.6'
    if level == 2:
        mesh_root += '_fine'

    mesh = Mesh(mesh_root + '.xml')
    boundaries = MeshFunction('size_t', mesh, mesh_root + '_facet_region.xml')
    ds = Measure('ds', domain=mesh, subdomain_data=boundaries)
    stabmethod = 'No stabilization'

    VE = VectorElement('P', mesh.ufl_cell(), velocity_degree)
    PE = FiniteElement('P', mesh.ufl_cell(), 1)
    W = FunctionSpace(mesh, VE * PE)

    u, p = TrialFunctions(W)
    v, q = TestFunctions(W)
    w = Function(W)
    u0, p0 = w.split()


    ####

    theta = Constant(1)
    k = Constant(1 / dt)
    mu = Constant(0.035)
    rho = Constant(1.2)
    eps = Constant(eps)





    U = (3 / 2) * 0.5 * Re * float(mu) / float(rho)

    print('\n Re = {}, U = {}\n'.format(Re, U))

    u_ = theta * u + (1 - theta) * u0
    theta_p = theta
    p_ = theta_p * p + (1 - theta_p) * p0

    laplace = mu * inner(grad(u_), grad(v)) * dx

    F = (
            k * rho * dot(u - u0, v) * dx
            + laplace
            - p_ * div(v) * dx + q * div(u) * dx
            + rho * dot(grad(u_) * u0, v) * dx
    )

    # F = (
    #     k*rho*dot(u - u0, v)*dx
    #     + mu*inner(grad(u_), grad(v))*dx
    #     - p_*div(v)*dx + q*div(u)*dx
    #     + rho*dot(grad(u_)*u0, v)*dx
    # )

    n = FacetNormal(mesh)
    h = CellDiameter(mesh)

    # eps = Constant(dt * float(mu) / (0.1 ** 2 * float(rho)))

    if temam:
        F += 0.5 * rho * div(u0) * dot(u_, v) * dx

    beta = Constant(1)               #TODO add initial values, probably 1
    gamma = Constant(gammagiv)

    backflow_func = 0.5 * rho * HF.abs_n(dot(u0, n)) * dot(u_, v) * ds(2) #0.5 * rho * HF.abs_n(div(u0)) * dot(u_, v) * dx


    param = 'No param'

    G = 0
    ### Added here beta parameter to the stabilization terms which we can control
    if bfs == 1:
        param = 'beta'
        stabmethod = 'velocity-penalization'
        G = 0.5 * rho * beta * dot(u0, n) * dot(u_, v) * ds(2)
        F -= G
    elif bfs == 2:
        param = 'beta'
        stabmethod = 'velocity-penalization negative part'
        G = 0.5 * rho * beta * HF.abs_n(dot(u0, n)) * dot(u_, v) * ds(2)
        F -= G
    elif bfs == 3:
        param = 'gamma'
        stabmethod = 'tangential penalization'
        Ctgt = h ** 2
        G = gamma * Ctgt * 0.5 * rho * HF.abs_n(dot(u0, n)) * (
                Dx(u[0], 1) * Dx(v[0], 1) + Dx(u[1], 1) * Dx(v[1], 1)) * ds(2)
    elif bfs == 4:
        param = 'gamma'
        stabmethod = 'tangential penalization - 2016 paper'
        Ctgt = h ** 2
        print(type(u0))
        max1 = assemble(HF.abs_n(u0)*ds(2))
        max2 = np.array(max1.array())
        max3 = abs(max2)
        maxi = max3.max()
        G = -1 * gamma * maxi * 0.5 * rho * Ctgt * (Dx(u[0], 1) * Dx(v[0], 1) + Dx(u[1], 1) * Dx(v[1], 1)) * ds(2)
        F -= G
    elif velocity_degree == 1 and float(eps):
        F += eps / mu * h ** 2 * inner(grad(p_), grad(q)) * dx

    # if temam:
    #     F += 0.5*rho*div(u0)*dot(u_, v)*dx
    #
    # if bfs == 1:
    #     F -= 0.5*rho*dot(u0, n)*dot(u_, v)*ds(2)
    # elif bfs == 2:
    #     F -= 0.5*rho*HF.abs_n(dot(u0, n))*dot(u_, v)*ds(2)
    # elif bfs == 3:
    #     Ctgt = h**2
    #     F -= Ctgt*0.5*rho*HF.abs_n(dot(u0, n))*(
    #         Dx(u[0], 1)*Dx(v[0], 1) + Dx(u[1], 1)*Dx(v[1], 1))*ds(2)
    #
    # elif velocity_degree == 1 and float(eps):
    #     F += eps/mu*h**2*inner(grad(p_), grad(q))*dx
    numerical = 0.5 * rho * k * dot(u_ - u0, u_ - u0) * dx
    stabilisationTest = backflow_func - G #+ laplace + numerical

    a = lhs(F)
    L = rhs(F)

    inflow = Expression(('sin(a*t*DOLFIN_PI)*U*(1 - pow(x[1], 2))', '0.'),
                        U=U, t=0., a=2.5, degree=2)
    # inflow = Expression(('U*(1 - pow(x[1], 2))', '0.'),
    #                     U=U, t=0., degree=2)
    bcs = [
        DirichletBC(W.sub(0), Constant((0, 0)), boundaries, 4),
        DirichletBC(W.sub(0), inflow, boundaries, 1),
        DirichletBC(W.sub(0).sub(1), Constant(0), boundaries, 3),
    ]

    A = assemble(a)

    if auto:
        runtype = "auto"
    elif param == 'beta':
        runtype = round(assemble(beta * ds(2)), 3)
    elif param == 'gamma':
        runtype = round(assemble(gamma * ds(2)))

    suf = 'bfs{}_tem{}_Re{}_'.format(int(bfs), int(temam), Re) + param + '_' + '{}_'.format(runtype)
    if velocity_degree == 1:
        suf = 'p1_' + suf
    suf = 'l{}_'.format(level) + suf

    xdmf_u = XDMFFile('results/u_' + suf + '.xdmf')
    xdmf_p = XDMFFile('results/p_' + suf + '.xdmf')
    xdmf_tau = XDMFFile('tau_sd_' + suf + '.xdmf')
    # xdmf_u.parameters['rewrite_function_mesh'] = False
    # xdmf_p.parameters['rewrite_function_mesh'] = False
    # xdmf_tau.parameters['rewrite_function_mesh'] = False

    u0.rename('u', 'u')
    p0.rename('p', 'p')

    w0 = Function(W)
    # r0, s0 = w0.split()
    #
    # w1 = Function(W)
    # r1, s1 = w1.split()

    # FINAL TIME
    T = 0.4

    # PLOTTING VECTORS
    # viscEnergyVec = np.zeros(((int)(T / dt), 1))
    # ToteviscEnergyVec = np.zeros(((int)(T / dt), 1))
    # incEnergyVec = np.zeros(((int)(T / dt), 1))
    # incEnergyVec2 = np.zeros(((int)(T / dt), 1))
    # numEnergyVec = np.zeros(((int)(T / dt), 1))
    # stabEnergyVec = np.zeros(((int)(T / dt), 1))
    # avgeig = np.zeros(((int)(T / dt), 1))
    #     print(type(F))

    pt = prog.progress_timer(description='Time Iterations', n_iter=40)
    # MAIN SOLVING LOOP
    eigvec = np.array([0, 0])
    for t in np.arange(dt, T + dt, dt):

        # print('t = {}'.format(round(t, 2)))

        #### May not be necessary ####
        w0.assign(w)
        r0, s0 = w0.split()

        inflow.t = t
        assemble(a, tensor=A)
        b = assemble(L)
        [bc.apply(A, b) for bc in bcs]
        solve(A, w.vector(), b)

        #### May not be necessary ####

        ###


        # w1.assign(w)
        # r1, s1 = w1.split()
        #
        # r1.vector().set_local(u0.vector().get_local() * (u0.vector().get_local() < 0))
        #
        # # ite +=1
        # # if ite==5:
        # #    plt.plot(r1.vector().get_local())
        # #    plt.plot(u0.vector().get_local())
        #
        # # print('|u|:', norm(u0))
        # # print('|p|:', norm(p0))
        # # print('div(u):', assemble(div(u0)*dx))
        #
        # ### This was trying to view U0 as a numpy array but didnt show anything meaningful ####
        # # for i in u0.vector().get_local():
        # #     print(i)
        # # print(u0.vector().get_local())
        #
        # # BACKFLOW KINETIC ENERGY CHANGE
        # BKE = assemble((rho / 2) * HF.abs_n(dot(r0, n)) * dot(u0, u0) * ds(2))

        # BACKFLOW VISCOUS ENERGY CHANGE
        # BVE = assemble(mu * inner(grad(r1),grad(r1)) * ds(2))
        # TVE = assemble(mu * inner(grad(u0),grad(u0))  * ds(2))
        # TVE = assemble(mu * inner(grad(u0), grad(u0)) * dx)

        #         print( (HF.abs_n(u0) != 0) )
        # BVEs = assemble(mu * np.abs(div(u0)) * div(r1) * ds(2))

        # TODO rework the backflowarea function so that it is one when there is backflow and 0 otherwise

        # ADDING TO VECTORS
        # viscEnergyVec[(int)(t / dt) - 1] = BVE
        # ToteviscEnergyVec[(int)(t / dt) - 1] = TVE
        #
        # incEnergyVec[(int)(t / dt) - 1] = BKE
        #
        # numEnergyVec[(int)(t / dt) - 1] = assemble((dot(u0 - r0, u0 - r0)) * ds(2))
        # print(numEnergyVec[(int)(t / dt) - 1])


        if bfs == 3 and auto:
            numericalfunc = 0#0.5 * rho * dot(u0 - r0, u0 - r0) * dx
            backflow_mat = assemble(lhs(backflow_func))
            backflow_vec = np.array(backflow_mat.array())
            #
            gamma.assign(1)
            while True:
                ### Building matrix and applying eigenvalues
                stabTensor = assemble(lhs(stabilisationTest + numericalfunc))
                # for bc in bcs: bc.apply(stabTensor)
                stabMatrix = np.array(stabTensor.array())
                # stabMatrix += np.eye(stabMatrix.shape[0])
                stabMatrix_backflow = stabMatrix * (backflow_vec != 0)
                stabMatrix_backflow_Nozero = stabMatrix_backflow[~(stabMatrix_backflow == 0).all(1)]

                # stabMatrix_sparse = sp.sparse.bsr_matrix(stabMatrix) # Sparse Version

                ### Creating reduced backflow matrix
                reduced_stabMatrix = np.transpose(
                    stabMatrix_backflow_Nozero.transpose()[~(stabMatrix_backflow_Nozero.transpose() == 0).all(1)])
                eigenvals_reduced_stabMatrix = LA.eigvals(reduced_stabMatrix)
                if plotcircles == 1:

                    circles = HF.GregsCircles(reduced_stabMatrix)
                    fig = HF.plotCircles(circles, round(t, 2), stabmethod, param, runtype)

                    if plotcircles == 2:
                        stabMatrix_sparse = sp.sparse.bsr_matrix(stabMatrix)  # Sparse Version
                        small_eigenvals_stabMatrix = ssl.eigs(stabMatrix_sparse, 5, sigma=-10, which='LM', return_eigenvectors=False)
                        for EV in small_eigenvals_stabMatrix:
                            plt.plot(EV.real, EV.imag, 'wo')

                    for eigval in eigenvals_reduced_stabMatrix:
                        plt.plot(eigval.real, eigval.imag, 'r+')
                    fig.savefig('circles/' + str(round(t*100)) + 'gersh.png')
                    plt.close(fig)

                if eigenvals_reduced_stabMatrix.size == 0:
                    del stabTensor, stabMatrix, reduced_stabMatrix, eigenvals_reduced_stabMatrix
                    break
                if eigenvals_reduced_stabMatrix.min() >= 0:
                    del stabTensor, stabMatrix, reduced_stabMatrix, eigenvals_reduced_stabMatrix
                    break
                else:
                    del stabTensor, stabMatrix, reduced_stabMatrix, eigenvals_reduced_stabMatrix
                    gamma.assign(assemble(gamma * ds(2)) * 2)

            # print(round(assemble(gamma * ds(2))))
        elif (bfs == 1 or bfs == 2) and auto:
            numericalfunc = 0#0.5 * rho * dot(u0 - r0, u0 - r0) * dx
            #     # numericalEn = assemble(numericalfunc)
            #     # print(numericalEn)
            #
            backflow_mat = assemble(lhs(backflow_func))
            backflow_vec = np.array(backflow_mat.array())
            #
            beta.assign(1)
            betaold = 1
            betanew = 1
            while True:
                ### Building matrix and applying eigenvalues
                stabTensor = assemble(lhs(stabilisationTest + numericalfunc))
                # for bc in bcs: bc.apply(stabTensor)
                stabMatrix = np.array(stabTensor.array())
                # stabMatrix += np.eye(stabMatrix.shape[0])
                stabMatrix_backflow = stabMatrix * (backflow_vec != 0)
                stabMatrix_backflow_Nozero = stabMatrix_backflow[~(stabMatrix_backflow == 0).all(1)]



                ### Creating reduced backflow matrix
                reduced_stabMatrix = np.transpose(
                    stabMatrix_backflow_Nozero.transpose()[~(stabMatrix_backflow_Nozero.transpose() == 0).all(1)])
                eigenvals_reduced_stabMatrix = LA.eigvals(reduced_stabMatrix)
                if plotcircles == 1:

                    circles = HF.GregsCircles(reduced_stabMatrix)
                    fig = HF.plotCircles(circles, round(t, 2), stabmethod, param, runtype)

                    if plotcircles == 2:
                        stabMatrix_sparse = sp.sparse.bsr_matrix(stabMatrix)  # Sparse Version
                        small_eigenvals_stabMatrix = ssl.eigs(stabMatrix_sparse, 5, sigma=-10, which='LM', return_eigenvectors=False)
                        for EV in small_eigenvals_stabMatrix:
                            plt.plot(EV.real, EV.imag, 'wo')


                    for eigval in eigenvals_reduced_stabMatrix:
                        plt.plot(eigval.real, eigval.imag, 'r+')
                    fig.savefig('circles/' + str(round(t*100)) + 'gersh.png')
                    plt.close(fig)

                if eigenvals_reduced_stabMatrix.size == 0:
                    del stabTensor, stabMatrix, reduced_stabMatrix, eigenvals_reduced_stabMatrix
                    break
                if eigenvals_reduced_stabMatrix.min() < 0 or betanew < 0.2:
                    del stabTensor, stabMatrix, reduced_stabMatrix, eigenvals_reduced_stabMatrix
                    beta.assign(betaold)
                    break
                else:
                    betaold = betanew
                    betanew -= 0.05
                    beta.assign(betanew)
                    del stabTensor, stabMatrix, reduced_stabMatrix, eigenvals_reduced_stabMatrix
        if plotcircles > 0 and not auto:
            numericalfunc = 0#0.5 * rho * dot(u0 - r0, u0 - r0) * dx
            backflow_mat = assemble(lhs(backflow_func))
            backflow_vec = np.array(backflow_mat.array())


            stabTensor = assemble(lhs(stabilisationTest + numericalfunc))
            # for bc in bcs: bc.apply(stabTensor)
            stabMatrix = np.array(stabTensor.array())
            stabMatrix_backflow = stabMatrix * (backflow_vec != 0)
            stabMatrix_backflow_Nozero = stabMatrix_backflow[~(stabMatrix_backflow == 0).all(1)]
            reduced_stabMatrix = np.transpose(
                stabMatrix_backflow_Nozero.transpose()[~(stabMatrix_backflow_Nozero.transpose() == 0).all(1)])
            eigenvals_reduced_stabMatrix = LA.eigvals(reduced_stabMatrix)
            circles = HF.GregsCircles(reduced_stabMatrix)
            fig = HF.plotCircles(circles, round(t, 2), stabmethod, param, runtype)
            if plotcircles == 2 and eigenvals_reduced_stabMatrix.size > 0:
                stabMatrix_sparse = sp.sparse.bsr_matrix(stabMatrix)  # Sparse Version
                # print(stabMatrix_sparse)
                small_eigenvals_stabMatrix = ssl.eigs(stabMatrix_sparse, 5, sigma=-10, which='LM', return_eigenvectors=False, v0=np.ones(stabMatrix_sparse.shape[0]))
                if t > 0.245 and t < 0.255:
                    eigvec = np.array([small_eigenvals_stabMatrix.min(), small_eigenvals_stabMatrix.max()])
                printlab = True
                for EV in small_eigenvals_stabMatrix:
                    if printlab:
                        plt.plot(EV.real, EV.imag, 'ko', label='Eigenvalues of full Matrix')
                        printlab = False
                    else:
                        plt.plot(EV.real, EV.imag, 'ko', label='_nolegend_')
                print(small_eigenvals_stabMatrix.min())
                del small_eigenvals_stabMatrix, stabMatrix_sparse
            printlab = True
            for eigval in eigenvals_reduced_stabMatrix:
                if printlab:
                    plt.plot(eigval.real, eigval.imag, 'r+', label='Eigenvalues of reduced Matrix')
                    printlab = False
                else:
                    plt.plot(eigval.real, eigval.imag, 'r+', label='_nolegend_')

            if eigenvals_reduced_stabMatrix.size > 0:
                plt.legend()
            fig.savefig('circles/' + str(round(t * 100)) + 'gersh.png')
            del stabTensor, stabMatrix, reduced_stabMatrix, eigenvals_reduced_stabMatrix
            plt.close(fig)
            # print(round(assemble(beta * ds(2)), 5))

        # print("stabilisationTest matrix is: " + HF.diag_dom(stabMatrix))
        #
        #
        # print("Reduced Matrix is: " + HF.diag_dom(reduced_stabMatrix))





        ### Print out the values for the energy changes at the current time step
        # print('Viscous energy change:', viscEnergyVec[(int)(t/dt) - 1])
        # print('Incoming energy change:', incEnergyVec[(int)(t/dt) - 1])
        # print('Numerical energy:', numEnergyVec[(int)(t/dt) - 1])

        xdmf_u.write(u0, t)
        xdmf_p.write(p0, t)
        pt.update()
    pt.finish()
    return eigvec


    # plt.figure()
    # # plt.plot(viscEnergyVec, 'b', label="Viscous")
    # # plt.plot(ToteviscEnergyVec, 'forestgreen', label="tot Viscous")
    # plt.plot(incEnergyVec, 'red', label="Incoming")
    # # plt.plot(numEnergyVec, 'yellow', label="Numerical")
    # # plt.plot(stabEnergyVec, 'orange', label='Stabilization')
    # plt.plot(ToteviscEnergyVec + numEnergyVec, 'deepskyblue', label='Total corrective energy')
    # plt.legend(loc='upper left')
    # plt.title('Energy changes of ' + stabmethod)
    # plt.show()

    del xdmf_u, xdmf_p


if __name__ == '__main__':
    Re = [5000]

    gammaVec = 10**np.arange(3.)

    eigsarr = []
    for Re_ in Re:
        for gamma in gammaVec:
            eigsarr.append(nse(Re_, level=1, temam=True, bfs=3, velocity_degree=1, eps=0.0001, dt=0.01, auto=False, plotcircles=2, gammagiv=gamma))

    fig = plt.figure(1)
    idx = 0
    for gamma in gammaVec:
        curreigsvec = eigsarr[0]
        plt.figure(1)
        plt.plot(gamma, abs(curreigsvec[0].real - curreigsvec[1].real), 'coral')
        idx += 1
    plt.legend("abs(maxeig - mineig)")
    plt.show()

        ## Weird results for the stabilization if bfs = 2,3. Stabilization Energy is too high

    # level:
    #   1:  coarse grid h = 0.05
    #   2:  medium grid h = 0.025

    # bfs:
    #   1:  (u.n)(u.v)
    #   2:  |u.n|_(u.v)  inertial
    #   3:  tangential

