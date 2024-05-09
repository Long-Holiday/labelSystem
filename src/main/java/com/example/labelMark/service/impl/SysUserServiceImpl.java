package com.example.labelMark.service.impl;

import cn.hutool.core.util.ObjectUtil;
import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.example.labelMark.domain.SysUser;
import com.example.labelMark.domain.SysUser;
import com.example.labelMark.mapper.SysUserMapper;
import com.example.labelMark.service.SysUserService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;

/**
 * <p>
 * 服务实现类
 * </p>
 *
 * @author wh
 * @since 2024-04-15
 */
@Service
public class SysUserServiceImpl extends ServiceImpl<SysUserMapper, SysUser> implements SysUserService {
    @Autowired
    private SysUserMapper SysUserMapper;

    /**
     * 创建用户
     *
     * @param user
     * @return
     */
    @Override
    public int createUser(SysUser user) {
        return SysUserMapper.insert(user);
    }

    @Override
    public SysUser findByUsername(String username) {
        QueryWrapper<SysUser> queryWrapper = new QueryWrapper();
//        queryWrapper.and(i -> i.eq("username", username)
//                .eq("userpassword", password));
        queryWrapper.eq("username", username);
        return getOne(queryWrapper);
    }

    @Override
    public SysUser findByUserId(Integer userid) {
        QueryWrapper<SysUser> queryWrapper = new QueryWrapper();
        queryWrapper.eq("userid", userid);
        return getOne(queryWrapper);
    }

    @Override
    public boolean resetPassword(SysUser user) {
//        重置密码为88888888
        user.setUserpassword(
                new BCryptPasswordEncoder().encode("88888888"));
        return saveOrUpdate(user);
    }

    @Override
    public long getUsersCountByAdmin(int isAdmin) {
        QueryWrapper<SysUser> queryWrapper = new QueryWrapper();
        queryWrapper.eq("isAdmin", isAdmin);
        long count = count(queryWrapper);
        return count;
    }

    @Override
    public long getTotalCount() {
        return count();
    }

    @Override
    public Page<SysUser> getUsersPage(Integer current, Integer pageSize, Integer userid, String username, Integer isAdmin) {
        Page<SysUser> userPage = new Page<SysUser>().setCurrent(current).setSize(pageSize);
        QueryWrapper<SysUser> SysUserQueryWrapper = new QueryWrapper<>();
        if (ObjectUtil.isNotNull(userid)) {
            SysUserQueryWrapper.eq("userid", userid);
        }
        if (StrUtil.isNotBlank(username)) {
            SysUserQueryWrapper.eq("username", username);
        }
        SysUserQueryWrapper.eq("isadmin", isAdmin);
        SysUserQueryWrapper.orderBy(true, true, "userid");
        return page(userPage, SysUserQueryWrapper);
    }

    @Override
    public boolean deleteUserById(Integer userid) {
        boolean isRemove = removeById(userid);
        return isRemove;
    }

    @Override
    public boolean updateUser(Integer userid, String username, Integer isadmin) {
        SysUser SysUser = new SysUser();
        SysUser.setUserid(userid);
        if (ObjectUtil.isNotNull(isadmin)) {
            SysUser.setIsadmin(isadmin);
        }
        if (StrUtil.isNotBlank(username)) {
            SysUser.setUsername(username);
        }
        boolean isUpdate = updateById(SysUser);
        return isUpdate;
    }
}
