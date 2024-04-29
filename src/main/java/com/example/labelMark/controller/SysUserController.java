package com.example.labelMark.controller;

import cn.hutool.core.util.ObjectUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.http.HttpRequest;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.labelMark.domain.Role;
import com.example.labelMark.domain.SysUser;
import com.example.labelMark.service.LoginService;
import com.example.labelMark.service.RoleService;
import com.example.labelMark.service.SysUserService;
import com.example.labelMark.utils.ResultGenerator;
import com.example.labelMark.vo.LoginUser;
import com.example.labelMark.vo.constant.Result;
import io.swagger.annotations.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.web.bind.annotation.*;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpSession;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * <p>
 * 用户业务控制器
 * </p>
 *
 * @author wh
 * @since 2024-04-15
 */
@RestController
@RequestMapping("/user")
@Api(tags = "用户业务控制器")
public class SysUserController {

    @Autowired
    SysUserService sysUserService;
    @Autowired
    RoleService roleService;
    @Autowired
    LoginService loginService;

    /**
     * TODO 注册需要增加校验，目前同用户名仍可以注册
     *
     * @return
     */
    @ApiOperation("注册")
    @RequestMapping(value = "/register", method = RequestMethod.POST)
    public Result register(@RequestBody Map<String, Object> map) {
        String username = ObjectUtil.toString(map.get("userName"));
        String password = ObjectUtil.toString(map.get("userPassword"));
        SysUser user = sysUserService.findByUsername(username);
        if (ObjectUtil.isNotNull(user)) {
            return ResultGenerator.getFailResult("用户已存在");
        }
        SysUser sysUser = new SysUser();
        sysUser.setUsername(username);
//        不为空，默认不是
        sysUser.setIsadmin(0);
        sysUser.setUserpassword(new BCryptPasswordEncoder().encode(password));
        int isCreated = sysUserService.createUser(sysUser);
        if (isCreated > 0) {
            return ResultGenerator.getSuccessResult("注册成功，账号：" + username);
        } else {
            return ResultGenerator.getFailResult("注册失败");
        }
    }

    @ApiOperation("登录")
    @PostMapping(value = "/login")
//   此参数待定，boolean isAutoLogin
    public Result login(@RequestBody Map<String, Object> map) {
        String username = ObjectUtil.toString(map.get("userName"));
        String password = ObjectUtil.toString(map.get("userPassword"));
        ;
        SysUser user = sysUserService.findByUsername(username);
        if (ObjectUtil.isNotNull(user)) {
            //        密码改为明码，和数据库的加密密码比对
            user.setUserpassword(password);
            Result result = loginService.login(user);
            return result;
        }
        return ResultGenerator.getFailResult("用户不存在");
    }

    @ApiOperation("密码重置")
    @RequestMapping(value = "/resetPassword", method = RequestMethod.POST)
    public Result resetPassword(@RequestParam Integer userid) {
        SysUser user = sysUserService.findByUserId(userid);
        if (ObjectUtil.isNotNull(user)) {
            boolean reset = sysUserService.resetPassword(user);
            if (reset) {
                return ResultGenerator.getSuccessResult("密码重置成功，密码为：88888888");
            } else {
                return ResultGenerator.getFailResult("密码重置失败");
            }
        }
        return ResultGenerator.getFailResult("用户不存在");
    }

    @ApiOperation("获取用户分页列表")
    @RequestMapping(value = "/getUsers", method = RequestMethod.POST)
    public Result getUsers(@RequestParam(required = false) Integer userid
            , @RequestParam(required = false) Integer isAdmin
            , @RequestParam Integer current
            , @RequestParam Integer pageSize
            , @RequestParam(required = false) String username) {
        try {
            long total;
            if (isAdmin != null) {
                total = sysUserService.getUsersCountByAdmin(isAdmin);
            } else {
                total = sysUserService.getTotalCount();
            }
            Page<SysUser> usersPage = sysUserService.getUsersPage(current, pageSize, userid, username);
            Map<String, Object> map = new HashMap<>();
            map.put("total", total);
            map.put("usersPage", usersPage);
            return ResultGenerator.getSuccessResult(map);
        } catch (Exception e) {
            return ResultGenerator.getFailResult("获取用户列表失败" + e.getMessage());
        }
    }

    @ApiOperation("删除用户")
    @RequestMapping(value = "/deleteUser", method = RequestMethod.POST)
    public Result deleteUser(@RequestParam Integer userid) {
        SysUser user = sysUserService.findByUserId(userid);
        if (ObjectUtil.isNotNull(user)) {
            boolean isRemove = sysUserService.deleteUserById(userid);
            if (isRemove) {
                return ResultGenerator.getSuccessResult("用户已删除");
            } else {
                return ResultGenerator.getFailResult("用户删除失败");
            }
        }
        return ResultGenerator.getFailResult("用户不存在");
    }

    @ApiOperation("获得所有角色")
    @RequestMapping(value = "/getRoles", method = RequestMethod.POST)
    public Result getRoles() {
        List<Role> roles = roleService.getRoles();
        return ResultGenerator.getSuccessResult(roles);
    }

    @ApiOperation("更新用户信息")
    @RequestMapping(value = "/updateUser", method = RequestMethod.POST)
    public Result updateUser(@RequestParam Integer userid
            , @RequestParam(required = false) String username, @RequestParam(required = false) Integer isadmin) {
        if (ObjectUtil.isNotNull(userid)) {
            boolean iaUpdateUser = sysUserService.updateUser(userid, username, isadmin);
            if (iaUpdateUser) {
                return ResultGenerator.getSuccessResult("用户信息更新成功");
            } else {
                return ResultGenerator.getFailResult("用户信息更新失败");
            }
        } else {
            return ResultGenerator.getFailResult("用户标识符不能为空");
        }
    }

    @ApiOperation("获取当前用户信息")
    @RequestMapping(value = "/currentState", method = RequestMethod.GET)
    public Map<String, Object> getCurrentState(HttpServletRequest request) {
//        直接从springSecurity框架中获得登录用户信息
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        UserDetails principal = (UserDetails) authentication.getPrincipal();
        String username = principal.getUsername();
        String password = principal.getPassword();
        SysUser user = sysUserService.findByUsername(username);
        Map<String, Object> map = new HashMap<>();
        map.put("currentUser", "");
        map.put("isAdmin", 0);
        if (ObjectUtil.isNotNull(user)) {
            map.put("currentUser", user);
            map.put("isAdmin", user.getIsadmin());
        }
        return map;
    }

    @ApiOperation("登出")
    @RequestMapping(value = "/logout", method = RequestMethod.POST)
    public Result logout() {
        Result result = loginService.logout();
        return result;
    }
}
